"""
Refactored document ingestion endpoints using IngestOrchestrator

This endpoint delegates all processing to the orchestrator pattern.
Much cleaner and more maintainable than inline processing.
"""
import datetime
import logging
from typing import Union, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form

# Import schemas
from schemas.api.responses.ingest import (
    SuccessfulIngestResponse,
    ExistingDocumentResponse,
    FailedIngestResponse,
    ScopeInfo
)
from schemas.api.requests.scope import DataScope, IngestScope, ScopeIdentifier
from schemas.validation import ValidationStatus

# Import orchestrator and context
from app.core.orchestrator import IngestOrchestrator
from app.core.orchestrator.pipeline_context import PipelineContext

# Import utilities
from app.config import settings
from app.core.auth import UserContext, get_current_user
from app.services.auth_service import get_auth_service_client
from api.utils.error_handler import get_user_friendly_error_message, log_error_with_context

# Import collection metadata updater
from api.endpoints.collections import update_collection_metadata
from app.core.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=Union[SuccessfulIngestResponse, ExistingDocumentResponse, FailedIngestResponse])
async def ingest_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    scope: IngestScope = Form(
        IngestScope.PRIVATE,
        description="Storage scope: 'private' (your documents - default) or 'shared' (organization documents)"
    ),
    collection_name: Optional[str] = Form(
        None,
        description="Optional collection name (must exist). If None, documents go to default space."
    ),
    user: UserContext = Depends(get_current_user)
):
    """
    Document ingest endpoint using IngestOrchestrator pattern

    Requires:
    - Valid JWT token in Authorization header
    - All organization members can upload to both PRIVATE and SHARED scopes

    Scope options:
    - PRIVATE (default): Store in user's private collection
    - SHARED: Store in organization shared collection

    Collection feature:
    - collection_name=None: Store in default space (user_{user_id}_chunks_1536)
    - collection_name="xyz": Store in named collection (must exist first)

    Pipeline stages:
    1. ValidationStage: Validate document
    2. ParsingStage: Extract text from PDF
    3. ChunkingStage: Token-based chunking with overlap
    4. EmbeddingStage: Generate embeddings
    5. IndexingStage: Insert into Milvus
    6. StorageStage: Upload to MinIO
    """
    start_time = datetime.datetime.now()

    # Convert IngestScope to DataScope
    data_scope = DataScope(scope.value)

    # Create scope identifier with optional collection name
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=collection_name  # If None, uses default collection
    )

    # If collection is specified, verify it exists
    if collection_name:
        from pymilvus import utility

        collection_milvus_name = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)
        if not utility.has_collection(collection_milvus_name):
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
            )

        # Verify exact collection name match from metadata
        try:
            minio_prefix = scope_id.get_object_prefix("docs")
            metadata_path = f"{minio_prefix}_collection_metadata.json"
            bucket = scope_id.get_bucket_name()
            client = storage.client_manager.get_client()

            response = client.get_object(bucket, metadata_path)
            import json
            collection_meta = json.loads(response.read().decode('utf-8'))

            original_collection_name = collection_meta.get("collection_name")

            if original_collection_name != collection_name:
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Could not verify collection name from metadata: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name}' not found in {scope.value} scope. Create it first using POST /collections"
            )

        logger.info(f"📁 Using existing collection: {collection_name}")

    logger.info(f"📄 Starting ingest for: {file.filename}")
    logger.info(f"👤 User: {user.user_id} (org: {user.organization_id})")
    logger.info(f"🎯 Scope: {scope} → Collection: {scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)}")

    try:
        # Read file data
        file_data = await file.read()

        # Generate document ID
        import hashlib
        file_hash = hashlib.md5(file_data).hexdigest()
        document_id = f"doc_{file_hash[:16]}"

        # Create pipeline context
        context = PipelineContext(
            file_data=file_data,
            filename=file.filename,
            document_id=document_id,
            scope_identifier=scope_id,
            user=user
        )

        # Create orchestrator and execute pipeline
        orchestrator = IngestOrchestrator()
        result = await orchestrator.process(context)

        # Handle pipeline result
        if not result.success:
            # Check if document already exists (validation stage returned EXISTS status)
            # Status might be string or enum, so check both
            status_is_exists = False
            if context.validation_result:
                if hasattr(context.validation_result.status, 'value'):
                    status_is_exists = (context.validation_result.status == ValidationStatus.EXISTS)
                else:
                    status_is_exists = (context.validation_result.status == 'exists' or context.validation_result.status == ValidationStatus.EXISTS.value)

            if status_is_exists:
                # Document already exists
                document_title = file.filename.replace('.pdf', '')
                if context.validation_result.existing_metadata:
                    document_title = context.validation_result.existing_metadata.get('document_title', document_title)

                return ExistingDocumentResponse(
                    document_id=document_id,
                    document_title=document_title,
                    processing_time=result.processing_time,
                    file_hash=file_hash,
                    message="Document already exists in database",
                    chunks_count=context.validation_result.existing_chunks_count or 0,
                    scope_info=ScopeInfo(
                        scope_type=scope.value,
                        collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                        bucket_name=scope_id.get_bucket_name()
                    ),
                    uploaded_at=datetime.datetime.now().isoformat()
                )

            # Other validation failure or pipeline error
            return FailedIngestResponse(
                document_id=document_id,
                document_title=file.filename.replace('.pdf', ''),
                processing_time=result.processing_time,
                file_hash=file_hash,
                message=result.message,
                error_details=result.error,
                scope_info=ScopeInfo(
                    scope_type=scope.value,
                    collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                    bucket_name=scope_id.get_bucket_name()
                ),
                uploaded_at=datetime.datetime.now().isoformat()
            )

        # Success! Pipeline completed
        # Update collection metadata if using named collection
        if collection_name:
            try:
                update_collection_metadata(scope_id)
            except Exception as meta_error:
                logger.warning(f"Failed to update collection metadata: {meta_error}")

        # Calculate tokens used (estimate from embeddings)
        total_embedding_tokens = sum(
            len(emb) for emb in context.embeddings
        ) if context.embeddings else 0

        # Report usage to auth service
        auth_client = get_auth_service_client()
        remaining_credits = user.remaining_credits

        try:
            usage_result = await auth_client.consume_usage(
                user_id=user.user_id,
                service_type="rag_ingest",
                tokens_used=total_embedding_tokens,
                processing_time=result.processing_time,
                metadata={
                    "filename": file.filename,
                    "chunks_created": result.chunks_created,
                    "pages_count": len(context.pages) if context.pages else 0,
                    "file_size_bytes": len(file_data),
                    "document_type": context.validation_result.document_type if context.validation_result else "unknown"
                }
            )

            if usage_result.get("remaining_credits") is not None:
                remaining_credits = usage_result.get("remaining_credits")

        except Exception as e:
            logger.warning(f"Failed to report usage to auth service: {str(e)}")

        # Prepare detailed response with new fields
        document_title = file.filename.replace('.pdf', '')
        if context.validation_result and context.validation_result.metadata:
            if context.validation_result.metadata.title:
                document_title = context.validation_result.metadata.title

        # Prepare chunking stats
        chunking_stats = None
        if context.stats:
            chunking_stats = {
                "method": context.stats.get('chunking_method', 'token-based'),
                "chunk_size_target": context.stats.get('chunk_size_config', 512),
                "chunk_overlap": context.stats.get('chunk_overlap_config', 50),
                "avg_tokens_per_chunk": context.stats.get('avg_chunk_tokens', 0),
                "avg_chars_per_chunk": context.stats.get('avg_chunk_chars', 0)
            }

        # Prepare stage timings
        stage_timings = {}
        for stage_name in context.completed_stages:
            duration_key = f"{stage_name}_duration_seconds"
            if duration_key in context.stats:
                stage_timings[stage_name] = context.stats[duration_key]

        # Extract validation status safely (might be string or enum)
        validation_status = None
        if context.validation_result:
            if hasattr(context.validation_result.status, 'value'):
                validation_status = context.validation_result.status.value
            else:
                validation_status = context.validation_result.status

        return SuccessfulIngestResponse(
            document_id=document_id,
            document_title=document_title,
            chunks_created=result.chunks_created,
            processing_time=result.processing_time,
            file_hash=file_hash,
            message=result.message,
            tokens_used=total_embedding_tokens,
            remaining_credits=remaining_credits,
            scope_info=ScopeInfo(
                scope_type=scope.value,
                collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                bucket_name=scope_id.get_bucket_name()
            ),
            uploaded_at=datetime.datetime.now().isoformat(),
            # NEW FIELDS
            validation_status=validation_status,
            validation_warnings=context.validation_result.warnings if context.validation_result else None,
            document_type=context.validation_result.document_type if context.validation_result else None,
            page_count=context.validation_result.metadata.page_count if (context.validation_result and context.validation_result.metadata) else None,
            chunking_stats=chunking_stats,
            stage_timings=stage_timings
        )

    except Exception as e:
        # Detailed error logging
        error_context = {
            "filename": file.filename if 'file' in locals() else "Unknown",
            "file_size": len(file_data) if 'file_data' in locals() else 0,
            "stage": "setup"
        }

        log_error_with_context(
            logger,
            e,
            "Document ingestion",
            error_context,
            level="ERROR"
        )

        user_message = get_user_friendly_error_message(e)
        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        return FailedIngestResponse(
            document_id=document_id if 'document_id' in locals() else "",
            document_title=file.filename.replace('.pdf', '') if 'file' in locals() else "",
            processing_time=processing_time,
            file_hash=file_hash if 'file_hash' in locals() else "",
            message=user_message,
            error_details=f"{type(e).__name__}: {str(e)}",
            scope_info=ScopeInfo(
                scope_type=scope.value,
                collection_name=scope_id.get_collection_name(settings.EMBEDDING_DIMENSION),
                bucket_name=scope_id.get_bucket_name()
            ),
            uploaded_at=datetime.datetime.now().isoformat()
        )
