"""
Collection-specific document ingestion endpoints

These endpoints provide a RESTful, collection-centric approach to document ingestion.
Unlike the general /ingest endpoint, these require a collection to exist first.
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
    FileIngestStatus,
    ScopeInfo
)
from schemas.api.requests.scope import DataScope, IngestScope, ScopeIdentifier
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
from app.config.constants import ServiceType

logger = logging.getLogger(__name__)
router = APIRouter()

# Import collection metadata updater
from api.endpoints.collections import update_collection_metadata


@router.post("/collections/{collection_name}/ingest", response_model=Union[SuccessfulIngestResponse, ExistingDocumentResponse, FailedIngestResponse])
@retry_with_backoff(max_retries=3)
async def ingest_to_collection(
    collection_name: str,  # Path parameter - collection name (mandatory)
    file: UploadFile = File(..., description="PDF file to upload"),
    scope: IngestScope = Form(
        IngestScope.PRIVATE,
        description="Storage scope: 'private' (your documents - default) or 'shared' (organization documents)"
    ),
    user: UserContext = Depends(get_current_user)  # Only JWT token required
):
    """
    Ingest a PDF document to a specific collection (RESTful approach)

    Requires:
    - Valid JWT token in Authorization header
    - Collection must exist (create it first using POST /collections)
    - All organization members can upload to both PRIVATE and SHARED scopes

    Path Parameters:
    - collection_name: Name of the collection to ingest into (mandatory)

    Scope options:
    - PRIVATE (default): Store in user's private collection
    - SHARED: Store in organization shared collection (accessible by all org members)

    This endpoint is collection-centric and requires the collection to exist before ingestion.
    For quick ingest without collections, use POST /ingest instead.
    """
    start_time = datetime.datetime.now()

    # Convert IngestScope to DataScope for ScopeIdentifier
    data_scope = DataScope(scope.value)

    # Create scope identifier with mandatory collection name
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=collection_name  # Mandatory from path
    )

    # Verify collection exists (mandatory check)
    from pymilvus import utility
    collection_milvus_name = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)
    if not utility.has_collection(collection_milvus_name):
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
        )

    # IMPORTANT: Verify exact collection name match from metadata
    # This prevents "sozlesme" from ingesting to "Sözleşme" collection
    try:
        minio_prefix = scope_id.get_object_prefix("docs")
        metadata_path = f"{minio_prefix}_collection_metadata.json"
        bucket = scope_id.get_bucket_name()
        from app.core.storage import storage
        client = storage.client_manager.get_client()

        response = client.get_object(bucket, metadata_path)
        import json
        collection_meta = json.loads(response.read().decode('utf-8'))

        # Get original collection name from metadata
        original_collection_name = collection_meta.get("collection_name")

        # Exact match required (case-sensitive, Turkish characters must match)
        if original_collection_name != collection_name:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
            )

    except HTTPException:
        raise
    except Exception as e:
        # If metadata doesn't exist, collection wasn't created properly
        logger.warning(f"Could not verify collection name from metadata: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
        )

    logger.info(f"📄 Starting collection-specific ingest for: {file.filename}")
    logger.info(f"👤 User: {user.user_id} (org: {user.organization_id})")
    logger.info(f"📁 Target collection: {collection_name} ({scope.value})")
    logger.info(f"🎯 Milvus collection: {collection_milvus_name}")

    try:
        # Document Validation Layer using Factory Pattern
        async with get_document_validator() as validator:
            validation_result = await validator.validate(file, milvus_manager, scope_id)

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

            logger.info(f"Document {validation_result.document_id} already exists in collection '{collection_name}'. Skipping ingestion.")

            return ExistingDocumentResponse(
                document_id=validation_result.document_id,
                document_title=document_title,
                processing_time=validation_result.processing_time,
                file_hash=validation_result.file_hash,
                message=f"Document already exists in collection '{collection_name}'",
                chunks_count=validation_result.existing_chunks_count or 0,
                scope_info=ScopeInfo(
                    scope_type=scope.value,
                    collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                    bucket_name=scope_id.get_bucket_name()
                ),
                uploaded_at=datetime.datetime.now().isoformat()
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
                error_details=error_message,
                scope_info=ScopeInfo(
                    scope_type=scope.value,
                    collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                    bucket_name=scope_id.get_bucket_name()
                ),
                uploaded_at=datetime.datetime.now().isoformat()
            )

        # Validation passed (VALID or WARNING status)
        # Use validated data for processing
        document_id = validation_result.document_id
        file_hash = validation_result.file_hash
        pdf_data = validation_result.pdf_data

        # Starting main processing
        # Upload to raw-documents bucket with validation metadata
        try:
            logger.info(f"[COLLECTION_INGEST] Uploading to collection '{collection_name}' for {document_id}")

            # Prepare enhanced metadata with validation results
            document_size_bytes = len(pdf_data)
            upload_metadata = {
                "document_id": document_id,
                "file_hash": file_hash,
                "original_filename": file.filename,
                "document_size_bytes": document_size_bytes,
                "document_type": validation_result.document_type,
                "validation_status": validation_result.status,
                "validation_timestamp": validation_result.validation_timestamp.isoformat(),
                "collection_name": collection_name  # Add collection name to metadata
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
                metadata=upload_metadata,
                scope=scope_id
            )
            if success:
                logger.info(f"[COLLECTION_INGEST] Upload successful for {document_id}/{file.filename}")
            else:
                logger.error(f"[COLLECTION_INGEST] Upload returned False for {document_id}")
        except Exception as e:
            logger.error(f"[COLLECTION_INGEST] Exception in upload: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[COLLECTION_INGEST] Traceback: {traceback.format_exc()}")

        # 1. PDF Parse (with validation hints)
        parser = PDFParser()
        pages, metadata = parser.extract_text(pdf_data)

        # Use validated metadata if parser metadata is missing
        if validation_result.metadata:
            document_title = validation_result.metadata.title or metadata.title or file.filename.replace('.pdf', '')
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

        logger.info(f"Created {len(chunks)} chunks for collection '{collection_name}'")

        # 3. Connect to scoped Milvus collection (auto-create for ingest operation)
        collection = milvus_manager.get_collection(scope_id, auto_create=True)

        # 4. Generate embeddings with batch processing
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = embedding_service.generate_embeddings_batch(chunk_texts)

        # 5. Prepare data for Milvus
        current_time = datetime.datetime.now()
        ids = [f"{document_id}_{i:04d}" for i in range(len(chunks))]
        document_ids = [document_id] * len(chunks)
        chunk_indices = list(range(len(chunks)))
        texts = chunk_texts

        # Prepare metadata for each chunk (with scope and collection info)
        combined_metadata = []
        for i, chunk in enumerate(chunks):
            meta = {
                "chunk_id": chunk.chunk_id,
                "page_number": chunk.page_number,
                "minio_object_path": f"{document_id}/{chunk.chunk_id}.json",
                "document_title": document_title,
                "file_hash": file_hash,
                "created_at": int(current_time.timestamp() * 1000),
                "document_size_bytes": document_size_bytes,
                "embedding_model": settings.EMBEDDING_MODEL,
                "embedding_dimension": len(embeddings[i]) if i < len(embeddings) else 1536,
                "embedding_size_bytes": len(embeddings[i]) * 4 if i < len(embeddings) else 1536 * 4,
                "document_type": validation_result.document_type,
                "validation_status": validation_result.status,
                # Multi-tenant metadata
                "organization_id": user.organization_id,
                "user_id": user.user_id if data_scope == DataScope.PRIVATE else None,
                "scope_type": data_scope.value,
                "uploaded_by": user.user_id,
                "uploaded_by_email": user.email,
                "collection_name": collection_name  # Add collection reference
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
                        "chunk_index": i,
                        "collection_name": collection_name
                    },
                    scope=scope_id
                )
            logger.info(f"Saved {len(chunks)} chunks to MinIO for collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Failed to save chunks to MinIO: {e}")

        # 6. Insert to Milvus
        logger.info(f"Inserting to Milvus collection '{collection_name}'...")

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

        # Update collection metadata after successful ingest
        try:
            update_collection_metadata(scope_id)
        except Exception as meta_error:
            logger.warning(f"Failed to update collection metadata: {meta_error}")

        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        # Calculate tokens used (estimate from embeddings)
        total_embedding_tokens = sum(len(emb) for emb in embeddings)

        # Report usage to auth service
        auth_client = get_auth_service_client()
        remaining_credits = user.remaining_credits

        try:
            usage_result = await auth_client.consume_usage(
                user_id=user.user_id,
                service_type=ServiceType.INGEST_COLLECTION,
                tokens_used=total_embedding_tokens,
                processing_time=processing_time,
                metadata={
                    "filename": file.filename,
                    "chunks_created": len(chunks),
                    "pages_count": len(pages),
                    "file_size_bytes": len(pdf_data),
                    "document_type": validation_result.document_type,
                    "collection_name": collection_name,
                    "scope": scope.value
                }
            )

            # Update credits from auth service response
            if usage_result.get("remaining_credits") is not None:
                remaining_credits = usage_result.get("remaining_credits")

        except Exception as e:
            # Log but don't fail the request (already processed)
            logger.warning(f"Failed to report usage to auth service: {str(e)}")

        logger.info(f"✅ Successfully ingested {len(chunks)} chunks to collection '{collection_name}' in {processing_time:.2f}s")

        # Include validation warnings in response message if any
        message = f"Document successfully ingested to collection '{collection_name}' with {len(chunks)} chunks"
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
            remaining_credits=remaining_credits,
            scope_info=ScopeInfo(
                scope_type=scope.value,
                collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                bucket_name=scope_id.get_bucket_name()
            ),
            uploaded_at=current_time.isoformat()
        )

    except Exception as e:
        # Detailed error logging with context
        error_context = {
            "filename": file.filename if 'file' in locals() else "Unknown",
            "file_size": len(pdf_data) if 'pdf_data' in locals() else 0,
            "stage": "validation" if 'validation_result' not in locals() else "processing",
            "collection_name": collection_name
        }

        log_error_with_context(
            logger,
            e,
            f"Collection ingest to '{collection_name}'",
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
            message=f"Failed to ingest to collection '{collection_name}': {user_message}",
            error_details=f"{type(e).__name__}: {str(e)}",
            scope_info=ScopeInfo(
                scope_type=scope.value,
                collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                bucket_name=scope_id.get_bucket_name()
            ),
            uploaded_at=datetime.datetime.now().isoformat()
        )


@router.post("/collections/{collection_name}/batch-ingest", response_model=BatchIngestResponse)
async def batch_ingest_to_collection(
    collection_name: str,  # Path parameter - collection name (mandatory)
    files: List[UploadFile] = File(...),
    scope: IngestScope = Form(
        IngestScope.PRIVATE,
        description="Storage scope: 'private' (your documents - default) or 'shared' (organization documents)"
    ),
    max_files: int = 10,
    user: UserContext = Depends(require_permission("documents", "upload"))
):
    """
    Batch ingest multiple PDF documents to a specific collection (RESTful approach)

    Requires:
    - Valid JWT token in Authorization header
    - User must have 'documents:upload' permission
    - Collection must exist (create it first using POST /collections)

    Path Parameters:
    - collection_name: Name of the collection to ingest into (mandatory)

    Scope options:
    - PRIVATE (default): Store in user's private collection
    - SHARED: Store in organization shared collection

    This endpoint is collection-centric and requires the collection to exist before ingestion.
    For quick batch ingest without collections, use POST /batch-ingest instead.
    """
    start_time = datetime.datetime.now()

    # Convert IngestScope to DataScope for ScopeIdentifier
    data_scope = DataScope(scope.value)

    # Create scope identifier with mandatory collection name
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=collection_name  # Mandatory from path
    )

    # Verify collection exists (mandatory check)
    from pymilvus import utility
    collection_milvus_name = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)
    if not utility.has_collection(collection_milvus_name):
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
        )

    # IMPORTANT: Verify exact collection name match from metadata
    # This prevents "sozlesme" from ingesting to "Sözleşme" collection
    try:
        minio_prefix = scope_id.get_object_prefix("docs")
        metadata_path = f"{minio_prefix}_collection_metadata.json"
        bucket = scope_id.get_bucket_name()
        from app.core.storage import storage
        client = storage.client_manager.get_client()

        response = client.get_object(bucket, metadata_path)
        import json
        collection_meta = json.loads(response.read().decode('utf-8'))

        # Get original collection name from metadata
        original_collection_name = collection_meta.get("collection_name")

        # Exact match required (case-sensitive, Turkish characters must match)
        if original_collection_name != collection_name:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
            )

    except HTTPException:
        raise
    except Exception as e:
        # If metadata doesn't exist, collection wasn't created properly
        logger.warning(f"Could not verify collection name from metadata: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
        )

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

    logger.info(f"📦 Starting batch ingest to collection '{collection_name}' for {len(files)} files")
    logger.info(f"👤 User: {user.user_id} (org: {user.organization_id})")
    logger.info(f"🎯 Scope: {scope} → Milvus collection: {collection_milvus_name}")

    # Process each file
    for file in files:
        file_start_time = datetime.datetime.now()

        try:
            # Read file data
            pdf_data = await file.read()
            file_hash = hashlib.md5(pdf_data).hexdigest()
            document_id = f"doc_{file_hash[:16]}"

            # Check if document already exists in scoped collection (auto-create for ingest operation)
            collection = milvus_manager.get_collection(scope_id, auto_create=True)
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
                    error=f"Document already exists in collection '{collection_name}'"
                ))
                logger.info(f"Skipped {file.filename} - already exists in '{collection_name}'")
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
            document_size_bytes = len(pdf_data)
            try:
                storage.upload_pdf_to_raw_documents(
                    document_id=document_id,
                    file_data=pdf_data,
                    filename=file.filename,
                    metadata={
                        "document_id": document_id,
                        "file_hash": file_hash,
                        "original_filename": file.filename,
                        "document_size_bytes": document_size_bytes,
                        "collection_name": collection_name
                    },
                    scope=scope_id
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
                    "document_size_bytes": document_size_bytes,
                    "embedding_model": settings.EMBEDDING_MODEL,
                    "embedding_dimension": len(embeddings[i]) if i < len(embeddings) else 1536,
                    "embedding_size_bytes": len(embeddings[i]) * 4 if i < len(embeddings) else 1536 * 4,
                    # Multi-tenant metadata
                    "organization_id": user.organization_id,
                    "user_id": user.user_id if data_scope == DataScope.PRIVATE else None,
                    "scope_type": data_scope.value,
                    "uploaded_by": user.user_id,
                    "uploaded_by_email": user.email,
                    "collection_name": collection_name  # Add collection reference
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

            logger.info(f"✅ Successfully ingested {file.filename} to collection '{collection_name}' with {len(chunks)} chunks")

        except Exception as e:
            # Failed
            failed += 1
            processing_time = (datetime.datetime.now() - file_start_time).total_seconds()

            # Log detailed error
            error_context = {
                "filename": file.filename,
                "batch_index": len(results) + 1,
                "total_files": len(files),
                "collection_name": collection_name
            }
            log_error_with_context(
                logger,
                e,
                f"Batch ingest to collection '{collection_name}' for {file.filename}",
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

    # Update collection metadata after batch ingest
    if successful > 0:
        try:
            update_collection_metadata(scope_id)
        except Exception as meta_error:
            logger.warning(f"Failed to update collection metadata after batch ingest: {meta_error}")

    logger.info(f"📊 Batch ingest to '{collection_name}' completed: {successful} successful, {failed} failed, {skipped} skipped")

    return BatchIngestResponse(
        total_files=len(files),
        successful=successful,
        failed=failed,
        skipped=skipped,
        results=results,
        total_processing_time=total_processing_time,
        message=f"Batch ingest to collection '{collection_name}': {successful} successful, {failed} failed, {skipped} skipped"
    )
