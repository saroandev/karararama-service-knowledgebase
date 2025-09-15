"""
Document ingestion endpoints
"""
import datetime
import hashlib
import json
import logging
from typing import List, Union
from dataclasses import dataclass
from fastapi import APIRouter, UploadFile, File, HTTPException

from api.models.responses import (
    SuccessfulIngestResponse,
    ExistingDocumentResponse,
    FailedIngestResponse,
    BatchIngestResponse,
    FileIngestStatus
)
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import retry_with_backoff
from api.core.embeddings import embedding_service
from app.config import settings
from app.storage import storage
from app.parse import PDFParser

logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass
class SimpleChunk:
    chunk_id: str
    text: str
    page_number: int


@router.post("/ingest", response_model=Union[SuccessfulIngestResponse, ExistingDocumentResponse, FailedIngestResponse])
@retry_with_backoff(max_retries=3)
async def ingest_document(file: UploadFile = File(...)):
    """
    Production PDF ingest endpoint with persistent storage
    """
    start_time = datetime.datetime.now()

    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        logger.info(f"Starting ingest for: {file.filename}")

        # Read PDF data
        pdf_data = await file.read()
        file_hash = hashlib.md5(pdf_data).hexdigest()

        # Generate document ID
        document_id = f"doc_{file_hash[:16]}"

        logger.info(f"Document ID: {document_id}, Hash: {file_hash}")

        # Early check for document existence to avoid unnecessary processing
        try:
            collection = milvus_manager.get_collection()
            search_existing = collection.query(
                expr=f'document_id == "{document_id}"',
                output_fields=['id', 'metadata'],
                limit=1
            )

            if search_existing:
                # Document already exists, return early
                processing_time = (datetime.datetime.now() - start_time).total_seconds()

                # Try to get the document title from existing metadata
                document_title = file.filename.replace('.pdf', '')
                if search_existing and 'metadata' in search_existing[0]:
                    try:
                        existing_metadata = search_existing[0]['metadata']
                        if isinstance(existing_metadata, str):
                            existing_metadata = json.loads(existing_metadata)
                        if isinstance(existing_metadata, dict):
                            document_title = existing_metadata.get('document_title', document_title)
                    except:
                        pass

                logger.info(f"Document {document_id} already exists. Skipping ingestion.")

                return ExistingDocumentResponse(
                    document_id=document_id,
                    document_title=document_title,
                    processing_time=processing_time,
                    file_hash=file_hash,
                    message="Document already exists in database",
                    chunks_count=len(search_existing)
                )
        except Exception as e:
            logger.warning(f"Could not check document existence: {e}. Proceeding with ingestion.")

        # Upload to raw-documents bucket with original filename
        try:
            logger.info(f"[INGEST] Calling upload_pdf_to_raw_documents for {document_id}")
            success = storage.upload_pdf_to_raw_documents(
                document_id=document_id,
                file_data=pdf_data,
                filename=file.filename,
                metadata={
                    "document_id": document_id,
                    "file_hash": file_hash,
                    "original_filename": file.filename
                }
            )
            if success:
                logger.info(f"[INGEST] Upload successful for {document_id}/{file.filename}")
            else:
                logger.error(f"[INGEST] Upload returned False for {document_id}")
                logger.error(f"[INGEST] Check storage.py logs for detailed error information")
        except Exception as e:
            logger.error(f"[INGEST] Exception in upload_pdf_to_raw_documents: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[INGEST] Traceback: {traceback.format_exc()}")

        # 1. PDF Parse
        parser = PDFParser()
        pages, metadata = parser.extract_text_from_pdf(pdf_data)

        document_title = metadata.title or file.filename.replace('.pdf', '')
        logger.info(f"Parsed {len(pages)} pages, title: {document_title}")

        # 2. Text chunking
        chunks = []
        for i, page in enumerate(pages):
            text = page.text.strip()
            if len(text) > 100:  # Skip very short pages
                chunk_id = f"{document_id}_{i:04d}"
                chunk = SimpleChunk(
                    chunk_id=chunk_id,
                    text=text,
                    page_number=page.page_number
                )
                chunks.append(chunk)

        logger.info(f"Created {len(chunks)} chunks")

        # 3. Connect to production Milvus
        collection = milvus_manager.get_collection()

        # 4. Generate embeddings with batch processing
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = embedding_service.generate_embeddings_batch(chunk_texts)

        # 5. Prepare data for Milvus
        current_time = datetime.datetime.now()
        ids = [f"{document_id}_{i:04d}" for i in range(len(chunks))]
        document_ids = [document_id] * len(chunks)
        chunk_indices = list(range(len(chunks)))
        texts = chunk_texts

        # Prepare metadata for each chunk
        combined_metadata = []
        for i, chunk in enumerate(chunks):
            meta = {
                "chunk_id": chunk.chunk_id,
                "page_number": chunk.page_number,
                "minio_object_path": f"{document_id}/{chunk.chunk_id}.json",
                "document_title": document_title,
                "file_hash": file_hash,
                "created_at": int(current_time.timestamp() * 1000)
            }
            combined_metadata.append(meta)

        # Save chunks to MinIO
        try:
            for i, (chunk_id, text) in enumerate(zip([c.chunk_id for c in chunks], texts)):
                storage.upload_chunk(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    chunk_text=text,
                    metadata={
                        "page_num": chunks[i].page_number,
                        "chunk_index": i
                    }
                )
            logger.info(f"Saved {len(chunks)} chunks to MinIO")
        except Exception as e:
            logger.error(f"Failed to save chunks to MinIO: {e}")

        # 6. Insert to Milvus
        logger.info("Inserting to production Milvus...")

        # Data order must match schema: id, document_id, chunk_index, text, embedding, metadata
        data = [
            ids,                 # id field (VARCHAR)
            document_ids,        # document_id field
            chunk_indices,       # chunk_index field
            texts,              # text field
            embeddings,          # embedding field
            combined_metadata    # metadata field (as dict, not JSON string)
        ]

        insert_result = collection.insert(data)
        collection.load()  # Reload for immediate search

        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        logger.info(f"Successfully ingested {len(chunks)} chunks in {processing_time:.2f}s")

        return SuccessfulIngestResponse(
            document_id=document_id,
            document_title=document_title,
            chunks_created=len(chunks),
            processing_time=processing_time,
            file_hash=file_hash,
            message=f"Document successfully ingested with {len(chunks)} chunks"
        )

    except Exception as e:
        logger.error(f"Ingest error: {str(e)}")
        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        return FailedIngestResponse(
            document_id=document_id if 'document_id' in locals() else "",
            document_title=document_title if 'document_title' in locals() else "",
            processing_time=processing_time,
            file_hash=file_hash if 'file_hash' in locals() else "",
            message=f"Ingest failed: {str(e)}",
            error_details=str(e)
        )


@router.post("/batch-ingest", response_model=BatchIngestResponse)
async def batch_ingest_documents(
    files: List[UploadFile] = File(...),
    parallel: bool = True,
    max_files: int = 10
):
    """
    Batch ingest multiple PDF documents
    """
    start_time = datetime.datetime.now()

    # Validate file count
    if len(files) > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {max_files} files allowed per batch"
        )

    # Validate all files are PDFs
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} is not a PDF. Only PDF files are supported"
            )

    results = []
    successful = 0
    failed = 0
    skipped = 0

    logger.info(f"Starting batch ingest for {len(files)} files")

    # Process each file
    for file in files:
        file_start_time = datetime.datetime.now()

        try:
            # Read file data
            pdf_data = await file.read()
            file_hash = hashlib.md5(pdf_data).hexdigest()
            document_id = f"doc_{file_hash[:16]}"

            # Check if document already exists
            collection = milvus_manager.get_collection()
            search_existing = collection.query(
                expr=f'document_id == "{document_id}"',
                output_fields=['id'],
                limit=1
            )

            if search_existing:
                # Document already exists
                skipped += 1
                processing_time = (datetime.datetime.now() - file_start_time).total_seconds()

                results.append(FileIngestStatus(
                    filename=file.filename,
                    status="skipped",
                    document_id=document_id,
                    file_hash=file_hash,
                    processing_time=processing_time,
                    error="Document already exists in database"
                ))
                logger.info(f"Skipped {file.filename} - already exists")
                continue

            # Process the document
            # Parse PDF
            parser = PDFParser()
            pages, metadata = parser.extract_text_from_pdf(pdf_data)

            document_title = metadata.title or file.filename.replace('.pdf', '')

            # Create chunks
            chunks = []
            for i, page in enumerate(pages):
                text = page.text.strip()
                if len(text) > 100:
                    chunk_id = f"{document_id}_{i:04d}"
                    chunk = SimpleChunk(
                        chunk_id=chunk_id,
                        text=text,
                        page_number=page.page_number
                    )
                    chunks.append(chunk)

            if not chunks:
                raise ValueError("No valid chunks created from document")

            # Upload to MinIO
            try:
                storage.upload_pdf_to_raw_documents(
                    document_id=document_id,
                    file_data=pdf_data,
                    filename=file.filename,
                    metadata={
                        "document_id": document_id,
                        "file_hash": file_hash,
                        "original_filename": file.filename
                    }
                )
            except Exception as e:
                logger.warning(f"MinIO upload failed for {file.filename}: {e}")

            # Generate embeddings
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = embedding_service.generate_embeddings_batch(chunk_texts)

            # Prepare data for Milvus
            current_time = datetime.datetime.now()
            ids = [f"{document_id}_{i:04d}" for i in range(len(chunks))]
            document_ids = [document_id] * len(chunks)

            combined_metadata = []
            for i, chunk in enumerate(chunks):
                meta = {
                    "chunk_id": chunk.chunk_id,
                    "page_number": chunk.page_number,
                    "document_title": document_title,
                    "file_hash": file_hash,
                    "created_at": int(current_time.timestamp() * 1000)
                }
                combined_metadata.append(meta)

            data = [
                ids,
                document_ids,
                [i for i in range(len(chunks))],  # chunk_indices
                chunk_texts,
                embeddings,
                combined_metadata
            ]

            collection.insert(data)
            collection.load()

            # Success
            successful += 1
            processing_time = (datetime.datetime.now() - file_start_time).total_seconds()

            results.append(FileIngestStatus(
                filename=file.filename,
                status="success",
                document_id=document_id,
                chunks_created=len(chunks),
                processing_time=processing_time,
                file_hash=file_hash
            ))

            logger.info(f"Successfully ingested {file.filename} with {len(chunks)} chunks")

        except Exception as e:
            # Failed
            failed += 1
            processing_time = (datetime.datetime.now() - file_start_time).total_seconds()

            results.append(FileIngestStatus(
                filename=file.filename,
                status="failed",
                processing_time=processing_time,
                error=str(e)
            ))

            logger.error(f"Failed to ingest {file.filename}: {str(e)}")

    total_processing_time = (datetime.datetime.now() - start_time).total_seconds()

    return BatchIngestResponse(
        total_files=len(files),
        successful=successful,
        failed=failed,
        skipped=skipped,
        results=results,
        total_processing_time=total_processing_time,
        message=f"Processed {len(files)} files: {successful} successful, {failed} failed, {skipped} skipped"
    )