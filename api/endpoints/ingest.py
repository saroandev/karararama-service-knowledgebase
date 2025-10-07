"""
Document ingestion endpoints with multi-tenant scope support
"""
import datetime
import hashlib
import logging
from typing import List, Union
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form

# Import from new schemas location
from schemas.api.responses.ingest import (
    SuccessfulIngestResponse,
    ExistingDocumentResponse,
    FailedIngestResponse,
    BatchIngestResponse,
    FileIngestStatus
)
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from schemas.internal.chunk import SimpleChunk
from schemas.validation import ValidationStatus

from api.core.milvus_manager import milvus_manager
from api.core.dependencies import retry_with_backoff
from api.core.embeddings import embedding_service
from app.config import settings
from app.core.storage import storage
from app.core.parsing import PDFParser
from app.core.validation.factory import get_document_validator
from api.utils.error_handler import (
    get_user_friendly_error_message,
    log_error_with_context
)
from app.core.auth import UserContext, require_permission, get_current_user
from app.services.auth_service import get_auth_service_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=Union[SuccessfulIngestResponse, ExistingDocumentResponse, FailedIngestResponse])
@retry_with_backoff(max_retries=3)
async def ingest_document(
    file: UploadFile = File(...),
    scope: DataScope = Form(DataScope.PRIVATE),
    user: UserContext = Depends(get_current_user)  # Only JWT token required, no specific permission
):
    """
    Multi-tenant PDF ingest endpoint with scope-based storage

    Requires:
    - Valid JWT token in Authorization header
    - Any authenticated user can upload to their PRIVATE scope
    - Only ADMIN role can upload to SHARED scope

    Scope options:
    - PRIVATE (default): Store in user's private collection/bucket (all users)
    - SHARED: Store in organization shared collection/bucket (admin only)
    """
    start_time = datetime.datetime.now()

    # Validate scope permissions
    if scope == DataScope.SHARED and user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can upload to shared scope. Please use 'private' scope."
        )

    # For private scope, user automatically has permission (it's their own data)

    # Create scope identifier
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=scope,
        user_id=user.user_id if scope == DataScope.PRIVATE else None
    )

    logger.info(f"📄 Starting ingest for: {file.filename}")
    logger.info(f"👤 User: {user.user_id} (org: {user.organization_id})")
    logger.info(f"🎯 Scope: {scope} → Collection: {scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)}")

    try:

        # Document Validation Layer using Factory Pattern
        async with get_document_validator() as validator:
            validation_result = await validator.validate(file, milvus_manager)

        # Log validation summary
        logger.info(f"Validation completed for {file.filename}: {validation_result.status}")
        if validation_result.warnings:
            logger.warning(f"Validation warnings: {validation_result.warnings}")

        # Handle duplicate document
        if validation_result.status == ValidationStatus.EXISTS:
            # Extract title from existing metadata
            document_title = file.filename.replace('.pdf', '')
            if validation_result.existing_metadata:
                document_title = validation_result.existing_metadata.get('document_title', document_title)

            logger.info(f"Document {validation_result.document_id} already exists. Skipping ingestion.")

            return ExistingDocumentResponse(
                document_id=validation_result.document_id,
                document_title=document_title,
                processing_time=validation_result.processing_time,
                file_hash=validation_result.file_hash,
                message="Document already exists in database",
                chunks_count=validation_result.existing_chunks_count or 0
            )

        # Handle invalid document
        if validation_result.status == ValidationStatus.INVALID:
            error_message = "; ".join(validation_result.errors) if validation_result.errors else "Validation failed"
            logger.error(f"Document validation failed: {error_message}")

            return FailedIngestResponse(
                document_id=validation_result.document_id,
                document_title=file.filename.replace('.pdf', ''),
                processing_time=validation_result.processing_time,
                file_hash=validation_result.file_hash,
                message=f"Document validation failed: {error_message}",
                error_details=error_message
            )

        # Validation passed (VALID or WARNING status)
        # Use validated data for processing
        document_id = validation_result.document_id
        file_hash = validation_result.file_hash
        pdf_data = validation_result.pdf_data


        # Starting main processing
        # Upload to raw-documents bucket with validation metadata
        try:
            logger.info(f"[INGEST] Calling upload_pdf_to_raw_documents for {document_id}")

            # Prepare enhanced metadata with validation results
            upload_metadata = {
                "document_id": document_id,
                "file_hash": file_hash,
                "original_filename": file.filename,
                "document_type": validation_result.document_type,
                "validation_status": validation_result.status,
                "validation_timestamp": validation_result.validation_timestamp.isoformat()
            }

            # Add extracted metadata if available
            if validation_result.metadata:
                upload_metadata["extracted_metadata"] = {
                    "title": validation_result.metadata.title,
                    "author": validation_result.metadata.author,
                    "page_count": validation_result.metadata.page_count,
                    "language": validation_result.metadata.language
                }

            # Add content info if available
            if validation_result.content_info:
                upload_metadata["content_analysis"] = validation_result.content_info

            success = storage.upload_pdf_to_raw_documents(
                document_id=document_id,
                file_data=pdf_data,
                filename=file.filename,
                metadata=upload_metadata
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

        # 1. PDF Parse (with validation hints)
        parser = PDFParser()
        pages, metadata = parser.extract_text(pdf_data)

        # Use validated metadata if parser metadata is missing
        if validation_result.metadata:
            document_title = validation_result.metadata.title or metadata.title or  file.filename.replace('.pdf', '')
        else:
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

        # 3. Connect to scoped Milvus collection
        collection = milvus_manager.get_collection(scope_id)

        # 4. Generate embeddings with batch processing
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = embedding_service.generate_embeddings_batch(chunk_texts)

        # 5. Prepare data for Milvus
        current_time = datetime.datetime.now()
        ids = [f"{document_id}_{i:04d}" for i in range(len(chunks))]
        document_ids = [document_id] * len(chunks)
        chunk_indices = list(range(len(chunks)))
        texts = chunk_texts

        # Prepare metadata for each chunk (with scope info)
        combined_metadata = []
        for i, chunk in enumerate(chunks):
            meta = {
                "chunk_id": chunk.chunk_id,
                "page_number": chunk.page_number,
                "minio_object_path": f"{document_id}/{chunk.chunk_id}.json",
                "document_title": document_title,
                "file_hash": file_hash,
                "created_at": int(current_time.timestamp() * 1000),
                "embedding_model": settings.EMBEDDING_MODEL,
                "embedding_dimension": len(embeddings[i]) if i < len(embeddings) else 1536,
                "embedding_size_bytes": len(embeddings[i]) * 4 if i < len(embeddings) else 1536 * 4,
                "document_type": validation_result.document_type,
                "validation_status": validation_result.status,
                # Multi-tenant metadata
                "organization_id": user.organization_id,
                "user_id": user.user_id if scope == DataScope.PRIVATE else None,
                "scope_type": scope.value,
                "uploaded_by": user.user_id
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

        collection.insert(data)
        collection.load()  # Reload for immediate search

        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        # Calculate tokens used (estimate from embeddings)
        total_embedding_tokens = sum(len(emb) for emb in embeddings)

        # Report usage to auth service
        auth_client = get_auth_service_client()
        remaining_credits = user.remaining_credits

        try:
            usage_result = await auth_client.consume_usage(
                user_id=user.user_id,
                service_type="rag_ingest",
                tokens_used=total_embedding_tokens,
                processing_time=processing_time,
                metadata={
                    "filename": file.filename,
                    "chunks_created": len(chunks),
                    "pages_count": len(pages),
                    "file_size_bytes": len(pdf_data),
                    "document_type": validation_result.document_type
                }
            )

            # Update credits from auth service response
            if usage_result.get("remaining_credits") is not None:
                remaining_credits = usage_result.get("remaining_credits")

        except Exception as e:
            # Log but don't fail the request (already processed)
            logger.warning(f"Failed to report usage to auth service: {str(e)}")

        logger.info(f"Successfully ingested {len(chunks)} chunks in {processing_time:.2f}s")

        # Include validation warnings in response message if any
        message = f"Document successfully ingested with {len(chunks)} chunks"
        if validation_result.warnings:
            message += f" (Warnings: {', '.join(validation_result.warnings)})"

        return SuccessfulIngestResponse(
            document_id=document_id,
            document_title=document_title,
            chunks_created=len(chunks),
            processing_time=processing_time,
            file_hash=file_hash,
            message=message,
            tokens_used=total_embedding_tokens,
            remaining_credits=remaining_credits
        )

    except Exception as e:
        # Detailed error logging with context
        error_context = {
            "filename": file.filename if 'file' in locals() else "Unknown",
            "file_size": len(pdf_data) if 'pdf_data' in locals() else 0,
            "stage": "validation" if 'validation_result' not in locals() else "processing"
        }

        log_error_with_context(
            logger,
            e,
            "Document ingestion",
            error_context,
            level="ERROR"
        )

        # Get user-friendly error message
        user_message = get_user_friendly_error_message(e)
        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        return FailedIngestResponse(
            document_id=document_id if 'document_id' in locals() else "",
            document_title=file.filename.replace('.pdf', '') if 'file' in locals() else "",
            processing_time=processing_time,
            file_hash=file_hash if 'file_hash' in locals() else "",
            message=user_message,
            error_details=f"{type(e).__name__}: {str(e)}"
        )


@router.post("/batch-ingest", response_model=BatchIngestResponse)
async def batch_ingest_documents(
    files: List[UploadFile] = File(...),
    max_files: int = 10,
    user: UserContext = Depends(require_permission("research", "ingest"))
):
    """
    Batch ingest multiple PDF documents

    Requires:
    - Valid JWT token in Authorization header
    - User must have 'research:ingest' permission
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
            pages, metadata = parser.extract_text(pdf_data)

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
                    "created_at": int(current_time.timestamp() * 1000),
                    "embedding_model": settings.EMBEDDING_MODEL,
                    "embedding_dimension": len(embeddings[i]) if i < len(embeddings) else 1536,
                    "embedding_size_bytes": len(embeddings[i]) * 4 if i < len(embeddings) else 1536 * 4  # float32 = 4 bytes
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

            # Log detailed error
            error_context = {
                "filename": file.filename,
                "batch_index": len(results) + 1,
                "total_files": len(files)
            }
            log_error_with_context(
                logger,
                e,
                f"Batch document ingestion for {file.filename}",
                error_context,
                level="ERROR"
            )

            # Get user-friendly error message
            user_error = get_user_friendly_error_message(e)

            results.append(FileIngestStatus(
                filename=file.filename,
                status="failed",
                processing_time=processing_time,
                error=user_error
            ))

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