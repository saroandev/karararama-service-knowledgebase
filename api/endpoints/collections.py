"""
Collection management endpoints

Provides CRUD operations for organizing documents into collections.
Collections are namespaces within a scope (private/shared) for better organization.
"""

import logging
import datetime
import time
import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse

from schemas.api.requests.collection import CreateCollectionRequest, UpdateCollectionRequest, CollectionQueryRequest
from schemas.api.requests.scope import DataScope, IngestScope, ScopeIdentifier
from schemas.api.responses.collection import (
    CreateCollectionResponse,
    ListCollectionsResponse,
    DeleteCollectionResponse,
    CollectionInfo,
    CollectionQueryResponse,
    CollectionSearchResult
)
from schemas.api.responses.document import DocumentInfo
from api.core.milvus_manager import milvus_manager  # LEGACY: Used for compatibility
from api.core.milvus_client_manager import milvus_client_manager  # NEW: MilvusClient API
from api.core.embeddings import embedding_service
from app.core.auth import UserContext, get_current_user
from app.core.storage import storage
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_collection_name(
    collection_name_input: str,
    scope_id: ScopeIdentifier,
    user: UserContext
) -> str:
    """
    Resolve collection name from URL input to original collection name

    Supports both:
    1. Original name with spaces: "bosluk denemesi"
    2. Sanitized name with hyphens: "bosluk-denemesi"

    This allows URLs to use hyphenated names (URL-friendly) while
    internally using the original collection name.

    Args:
        collection_name_input: Name from URL (may be hyphenated or original)
        scope_id: Scope identifier (will be updated with correct collection name)
        user: User context

    Returns:
        Original collection name from metadata

    Raises:
        HTTPException: If collection not found or name doesn't match
    """
    try:
        # Try to get metadata using the input name as-is first
        temp_scope = ScopeIdentifier(
            organization_id=scope_id.organization_id,
            scope_type=scope_id.scope_type,
            user_id=scope_id.user_id,
            collection_name=collection_name_input
        )

        minio_prefix = temp_scope.get_object_prefix("docs")
        metadata_path = f"{minio_prefix}_collection_metadata.json"
        bucket = temp_scope.get_bucket_name()
        client = storage.client_manager.get_client()

        response = client.get_object(bucket, metadata_path)
        import json
        collection_meta = json.loads(response.read().decode('utf-8'))

        # Get original collection name from metadata
        original_name = collection_meta.get("collection_name")
        sanitized_name = collection_meta.get("collection_name_sanitized")

        # Check if input matches either original or sanitized name
        if original_name == collection_name_input:
            # Exact match with original name
            return original_name
        elif sanitized_name == collection_name_input:
            # Match with sanitized name (URL-friendly)
            return original_name
        else:
            # Name doesn't match - collection not found
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection_name_input}' not found in {scope_id.scope_type.value} scope"
            )

    except HTTPException:
        raise
    except Exception as e:
        # If metadata doesn't exist, collection wasn't created properly
        logger.warning(f"Could not resolve collection name from metadata: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name_input}' not found in {scope_id.scope_type.value} scope"
        )


def update_collection_metadata(scope_id: ScopeIdentifier):
    """
    Update collection metadata statistics in MinIO after document ingestion

    This function recalculates and updates:
    - document_count: Number of unique documents
    - chunk_count: Total number of chunks
    - size_bytes: Total storage size
    - last_updated: Timestamp of last update

    Args:
        scope_id: Scope identifier with collection name

    Note: Silently fails if collection metadata doesn't exist (for backward compatibility)
    """
    try:
        minio_prefix = scope_id.get_object_prefix("docs")
        metadata_path = f"{minio_prefix}_collection_metadata.json"
        bucket = scope_id.get_bucket_name()
        client = storage.client_manager.get_client()

        # Check if metadata file exists
        try:
            response = client.get_object(bucket, metadata_path)
            import json
            collection_meta = json.loads(response.read().decode('utf-8'))
        except Exception:
            # Metadata file doesn't exist (default space or collection not created via API)
            logger.debug(f"Collection metadata not found at {metadata_path}, skipping update")
            return

        # Get collection from Milvus
        milvus_collection_name = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)

        # Ensure Milvus connection exists
        milvus_manager.get_connection()
        if not utility.has_collection(milvus_collection_name):
            logger.warning(f"Milvus collection {milvus_collection_name} not found, skipping metadata update")
            return

        collection = milvus_manager.get_collection(scope_id)

        # Calculate current statistics
        try:
            stats = collection.query(
                expr="id > 0",  # INT64 primary key (changed from 'id != ""')
                output_fields=["id", "document_id", "metadata"],
                limit=16384  # Max limit
            )

            chunk_count = len(stats)
            document_ids = set(item["document_id"] for item in stats)
            document_count = len(document_ids)

            # Calculate size from metadata
            size_bytes = 0
            for item in stats:
                meta = item.get("metadata", {})
                doc_size = meta.get("document_size_bytes", 0) if isinstance(meta, dict) else 0
                size_bytes += doc_size

            # Divide by chunk count to get approximate document size (since each chunk has the same document_size_bytes)
            size_bytes = size_bytes // max(chunk_count, 1) * document_count if chunk_count > 0 else 0

        except Exception as e:
            logger.warning(f"Could not calculate collection stats: {e}")
            return

        # Update statistics in metadata
        current_time = datetime.datetime.now().isoformat()
        collection_meta["statistics"] = {
            "document_count": document_count,
            "chunk_count": chunk_count,
            "size_bytes": size_bytes,
            "last_updated": current_time
        }

        # Write updated metadata back to MinIO
        import json
        import io
        metadata_json = json.dumps(collection_meta, ensure_ascii=False, indent=2).encode('utf-8')

        client.put_object(
            bucket,
            metadata_path,
            io.BytesIO(metadata_json),
            len(metadata_json),
            content_type="application/json"
        )

        logger.info(f"✅ Updated collection metadata: {document_count} docs, {chunk_count} chunks, {size_bytes} bytes")

    except Exception as e:
        # Don't fail the ingest if metadata update fails
        logger.warning(f"Failed to update collection metadata: {e}")


def _check_collection_permission(user: UserContext, scope: IngestScope, operation: str):
    """
    Check if user has permission for collection operation

    Args:
        user: User context
        scope: Collection scope
        operation: Operation type (create, delete, etc.)

    Raises:
        HTTPException: If user doesn't have permission
    """
    # SHARED collections require ADMIN role
    if scope == IngestScope.SHARED and user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail=f"Only administrators can {operation} shared collections"
        )

    # PRIVATE collections: users can manage their own
    # (already authenticated, so no additional check needed)


def _get_collection_info(
    collection_name: str,
    scope_id: ScopeIdentifier,
    user: UserContext
) -> CollectionInfo:
    """
    Get collection information including stats

    Args:
        collection_name: Collection name
        scope_id: Scope identifier with collection name
        user: User context

    Returns:
        CollectionInfo object
    """
    milvus_collection_name = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)
    minio_prefix = scope_id.get_object_prefix("docs")

    # Ensure Milvus connection exists
    milvus_manager.get_connection()

    # Check if collection exists in Milvus
    if not utility.has_collection(milvus_collection_name):
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found in {scope_id.scope_type.value} scope"
        )

    # Get collection from Milvus (do NOT auto-create in read operations)
    collection = milvus_manager.get_collection(scope_id, auto_create=False)

    # Get statistics
    try:
        stats = collection.query(
            expr="id > 0",  # INT64 primary key (changed from 'id != ""')
            output_fields=["id", "document_id"],
            limit=16384  # Max limit
        )

        chunk_count = len(stats)
        document_ids = set(item["document_id"] for item in stats)
        document_count = len(document_ids)

    except Exception as e:
        logger.warning(f"Could not get collection stats: {e}")
        chunk_count = 0
        document_count = 0

    # Calculate storage size (approximate from MinIO)
    size_bytes = 0
    try:
        client = storage.client_manager.get_client()
        bucket = scope_id.get_bucket_name()

        objects = client.list_objects(bucket, prefix=minio_prefix, recursive=True)
        for obj in objects:
            size_bytes += obj.size
    except Exception as e:
        logger.warning(f"Could not calculate storage size: {e}")

    # Get metadata from MinIO (if exists)
    metadata = None
    description = None
    created_at = datetime.datetime.now().isoformat()
    created_by = user.user_id  # Default to current user
    created_by_email = user.email  # Default to current user email
    updated_at = None
    original_collection_name = collection_name  # Fallback to sanitized name if metadata not found

    try:
        # Check for collection metadata file
        metadata_path = f"{minio_prefix}_collection_metadata.json"
        client = storage.client_manager.get_client()
        bucket = scope_id.get_bucket_name()

        response = client.get_object(bucket, metadata_path)
        import json
        collection_meta = json.loads(response.read().decode('utf-8'))

        description = collection_meta.get("description")
        metadata = collection_meta.get("metadata")
        created_at = collection_meta.get("created_at", created_at)
        created_by = collection_meta.get("created_by", user.user_id)
        created_by_email = collection_meta.get("created_by_email", user.email)

        # Get original collection name from metadata (with spaces, Turkish chars, etc.)
        if "collection_name" in collection_meta:
            original_collection_name = collection_meta.get("collection_name")

        # Get last_updated from statistics if available
        stats = collection_meta.get("statistics", {})
        updated_at = stats.get("last_updated")

    except Exception:
        # No metadata file exists yet - use sanitized name as fallback
        pass

    # Calculate size in MB
    size_mb = round(size_bytes / (1024 * 1024), 2) if size_bytes > 0 else 0.0

    return CollectionInfo(
        name=original_collection_name,
        scope=scope_id.scope_type.value,
        description=description,
        document_count=document_count,
        chunk_count=chunk_count,
        created_at=created_at,
        created_by=created_by,
        created_by_email=created_by_email,
        updated_at=updated_at,
        size_bytes=size_bytes,
        size_mb=size_mb,
        metadata=metadata,
        milvus_collection_name=milvus_collection_name,
        minio_prefix=minio_prefix
    )


@router.post("/create_collection", response_model=CreateCollectionResponse)
async def create_collection(
    request: CreateCollectionRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Create a new collection

    Requires:
    - Valid JWT token
    - Admin role for SHARED collections

    Creates:
    - Milvus collection with appropriate naming
    - MinIO metadata file
    """
    logger.info(f"Creating collection '{request.name}' in {request.scope} scope")

    # Check permissions
    _check_collection_permission(user, request.scope, "create")

    # Convert scope
    data_scope = DataScope(request.scope.value)

    # Create scope identifier with collection name
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if request.scope == IngestScope.PRIVATE else None,
        collection_name=request.name
    )

    # Check if collection already exists
    collection_name = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)

    # Ensure Milvus connection exists
    milvus_manager.get_connection()

    # NOTE: utility.has_collection() throws MilvusException if collection doesn't exist
    # This is a pymilvus quirk - we catch it and treat as "collection doesn't exist"
    collection_exists = False
    try:
        collection_exists = utility.has_collection(collection_name)
    except Exception as e:
        # If error is "can't find collection", it means collection doesn't exist (expected)
        if "can't find collection" not in str(e) and "collection not found" not in str(e):
            # Unexpected error - re-raise
            logger.error(f"Unexpected error checking collection existence: {e}")
            raise
        # Collection doesn't exist - this is what we want for creation
        logger.debug(f"Collection {collection_name} doesn't exist (expected for new collection)")

    if collection_exists:
        raise HTTPException(
            status_code=409,
            detail=f"Collection '{request.name}' already exists in {request.scope} scope"
        )

    try:
        # Create Milvus collection (auto-create for create operation)
        milvus_manager.get_collection(scope_id, auto_create=True)
        logger.info(f"Created Milvus collection: {collection_name}")

        # Save metadata to MinIO
        current_time = datetime.datetime.now().isoformat()
        metadata_content = {
            "collection_name": request.name,  # Original name with spaces for display
            "collection_name_sanitized": scope_id._sanitize_for_minio(request.name),  # Sanitized for MinIO paths
            "scope": request.scope.value,
            "description": request.description,
            "metadata": request.metadata,
            "created_at": current_time,
            "created_by": user.user_id,
            "created_by_email": user.email,
            "organization_id": user.organization_id,
            "statistics": {
                "document_count": 0,
                "chunk_count": 0,
                "size_bytes": 0,
                "last_updated": current_time
            }
        }

        import json
        import io
        metadata_json = json.dumps(metadata_content, ensure_ascii=False, indent=2).encode('utf-8')

        client = storage.client_manager.get_client()
        bucket = scope_id.get_bucket_name()

        # Ensure bucket exists
        storage.client_manager.ensure_scope_bucket(scope_id)

        # Upload metadata
        metadata_path = f"{scope_id.get_object_prefix('docs')}_collection_metadata.json"
        client.put_object(
            bucket,
            metadata_path,
            io.BytesIO(metadata_json),
            len(metadata_json),
            content_type="application/json"
        )

        logger.info(f"Saved collection metadata to MinIO: {metadata_path}")

        # Build CollectionInfo directly without querying Milvus
        # New collection is empty, so all stats are 0
        collection_info = CollectionInfo(
            name=request.name,
            scope=request.scope.value,
            description=request.description,
            document_count=0,
            chunk_count=0,
            created_at=current_time,
            created_by=user.user_id,
            created_by_email=user.email,
            updated_at=None,
            size_bytes=0,
            size_mb=0.0,
            metadata=request.metadata,
            milvus_collection_name=collection_name,
            minio_prefix=scope_id.get_object_prefix("docs")
        )

        response_data = CreateCollectionResponse(
            message=f"Collection '{request.name}' created successfully in {request.scope} scope",
            collection=collection_info
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=response_data.model_dump()
        )

    except Exception as e:
        logger.error(f"Failed to create collection: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create collection: {str(e)}"
        )


@router.get("/collections", response_model=ListCollectionsResponse)
async def list_collections(
    scope: Optional[str] = Query(
        None,
        description="Filter by scope: 'private', 'shared', or 'all' (default: all)"
    ),
    user: UserContext = Depends(get_current_user)
):
    """
    List all collections accessible by the user

    Scope filtering:
    - private: Only user's private collections
    - shared: Only organization shared collections
    - all or None: Both private and shared
    """
    logger.info(f"Listing collections for user {user.user_id}, scope filter: {scope}")

    collections: List[CollectionInfo] = []

    # Determine which scopes to check
    check_private = scope in [None, "all", "private"]
    check_shared = scope in [None, "all", "shared"]

    # Get all Milvus collections (automatically handles connection)
    all_collections = milvus_manager.list_all_collections()

    # Filter private collections
    if check_private and user.data_access.own_data:
        safe_user_id = user.user_id.replace('-', '_')
        private_prefix = f"user_{safe_user_id}_col_"

        for coll_name in all_collections:
            if coll_name.startswith(private_prefix) and "_chunks_" in coll_name:
                # Extract collection name
                # Format: user_{user_id}_col_{collection_name}_chunks_{dimension}
                parts = coll_name.split("_col_")
                if len(parts) == 2:
                    collection_part = parts[1].split("_chunks_")[0]

                    try:
                        scope_id = ScopeIdentifier(
                            organization_id=user.organization_id,
                            scope_type=DataScope.PRIVATE,
                            user_id=user.user_id,
                            collection_name=collection_part
                        )

                        collection_info = _get_collection_info(collection_part, scope_id, user)
                        collections.append(collection_info)
                    except Exception as e:
                        logger.warning(f"Could not get info for collection {coll_name}: {e}")

    # Filter shared collections
    if check_shared and user.data_access.shared_data:
        safe_org_id = user.organization_id.replace('-', '_')
        shared_prefix = f"org_{safe_org_id}_col_"

        for coll_name in all_collections:
            if coll_name.startswith(shared_prefix) and "_chunks_" in coll_name:
                # Extract collection name
                # Format: org_{org_id}_col_{collection_name}_chunks_{dimension}
                parts = coll_name.split("_col_")
                if len(parts) == 2:
                    collection_part = parts[1].split("_chunks_")[0]

                    try:
                        scope_id = ScopeIdentifier(
                            organization_id=user.organization_id,
                            scope_type=DataScope.SHARED,
                            collection_name=collection_part
                        )

                        collection_info = _get_collection_info(collection_part, scope_id, user)
                        collections.append(collection_info)
                    except Exception as e:
                        logger.warning(f"Could not get info for collection {coll_name}: {e}")

    # Sort by created_at descending
    collections.sort(key=lambda x: x.created_at, reverse=True)

    return ListCollectionsResponse(
        total_count=len(collections),
        collections=collections,
        scope_filter=scope
    )


@router.get("/collections/{collection_name}", response_model=CollectionInfo)
async def get_collection(
    collection_name: str,
    scope: IngestScope = Query(..., description="Collection scope: 'private' or 'shared'"),
    user: UserContext = Depends(get_current_user)
):
    """
    Get detailed information about a specific collection

    Supports both original names and URL-friendly hyphenated names:
    - "bosluk denemesi" (original with spaces)
    - "bosluk-denemesi" (URL-friendly with hyphens)
    """
    logger.info(f"Getting collection '{collection_name}' in {scope} scope")

    # Convert scope
    data_scope = DataScope(scope.value)

    # Create temporary scope identifier for name resolution
    temp_scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=collection_name
    )

    # Check access
    if data_scope == DataScope.PRIVATE and not user.data_access.own_data:
        raise HTTPException(status_code=403, detail="No access to private collections")

    if data_scope == DataScope.SHARED and not user.data_access.shared_data:
        raise HTTPException(status_code=403, detail="No access to shared collections")

    # Resolve collection name (handles both original and hyphenated names)
    original_collection_name = _resolve_collection_name(collection_name, temp_scope_id, user)

    # Create scope identifier with resolved original name
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=original_collection_name
    )

    return _get_collection_info(original_collection_name, scope_id, user)


@router.delete("/collections/{collection_name}", response_model=DeleteCollectionResponse)
async def delete_collection(
    collection_name: str,
    scope: IngestScope = Query(..., description="Collection scope: 'private' or 'shared'"),
    user: UserContext = Depends(get_current_user)
):
    """
    Delete a collection and all its data

    Requires:
    - Admin role for SHARED collections
    - Owner for PRIVATE collections

    Deletes:
    - Milvus collection and all vectors
    - All documents and chunks from MinIO

    Supports both original names and URL-friendly hyphenated names:
    - "bosluk denemesi" (original with spaces)
    - "bosluk-denemesi" (URL-friendly with hyphens)
    """
    logger.info(f"Deleting collection '{collection_name}' in {scope} scope")

    # Check permissions
    _check_collection_permission(user, scope, "delete")

    # Convert scope
    data_scope = DataScope(scope.value)

    # Create temporary scope identifier for name resolution
    temp_scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=collection_name
    )

    # Try to resolve collection name (handles both original and hyphenated names)
    # If resolution fails, it will raise HTTPException 404
    try:
        original_collection_name = _resolve_collection_name(collection_name, temp_scope_id, user)
        logger.info(f"✅ Collection name resolved: '{collection_name}' -> '{original_collection_name}'")
    except HTTPException:
        # Resolution failed - collection not found
        raise
    except Exception as e:
        # Metadata doesn't exist - this may be an old collection or inconsistent state
        # Allow deletion to proceed to clean up orphaned Milvus collections
        logger.warning(f"⚠️ Could not resolve collection name: {e}")
        logger.warning(f"💡 Proceeding with deletion anyway to clean up Milvus collection")
        original_collection_name = collection_name

    # Create scope identifier with resolved original name
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=original_collection_name
    )

    # Get collection info before deleting
    try:
        collection_info = _get_collection_info(original_collection_name, scope_id, user)
        documents_deleted = collection_info.document_count
        chunks_deleted = collection_info.chunk_count
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Could not get collection info before deletion: {e}")
        documents_deleted = 0
        chunks_deleted = 0

    try:
        # Drop Milvus collection
        collection_name_milvus = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)

        # Ensure Milvus connection exists
        milvus_manager.get_connection()
        if utility.has_collection(collection_name_milvus):
            from pymilvus import Collection
            collection = Collection(collection_name_milvus)
            collection.drop()
            logger.info(f"✅ Dropped Milvus collection: {collection_name_milvus}")

        # Delete entire collection folder from MinIO (docs/ + chunks/ + metadata)
        client = storage.client_manager.get_client()
        bucket = scope_id.get_bucket_name()

        # Get collection folder path based on scope (uses sanitized collection name)
        # scope_id.get_object_prefix() already sanitizes the collection name for MinIO paths
        # Private: users/{user_id}/collections/{sanitized_name}/
        # Shared: shared/collections/{sanitized_name}/
        sanitized_collection_name = scope_id._sanitize_for_minio(original_collection_name)
        if scope_id.scope_type == DataScope.PRIVATE:
            collection_folder_prefix = f"users/{scope_id.user_id}/collections/{sanitized_collection_name}/"
        else:  # SHARED
            collection_folder_prefix = f"shared/collections/{sanitized_collection_name}/"

        logger.info(f"🗑️  Deleting MinIO folder: {bucket}/{collection_folder_prefix}")

        # List all objects in collection folder (recursive to get docs/, chunks/, and metadata)
        objects_to_delete = client.list_objects(bucket, prefix=collection_folder_prefix, recursive=True)

        deleted_count = 0
        failed_count = 0
        for obj in objects_to_delete:
            try:
                client.remove_object(bucket, obj.object_name)
                deleted_count += 1
                logger.debug(f"Deleted: {obj.object_name}")
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Error deleting object {obj.object_name}: {e}")

        if failed_count > 0:
            logger.warning(f"⚠️  Deleted {deleted_count} objects, {failed_count} failed for collection '{collection_name}'")
            message = f"Collection '{collection_name}' deleted from {scope} scope with warnings ({failed_count} files failed to delete)"
        else:
            logger.info(f"✅ Deleted {deleted_count} objects from MinIO for collection '{collection_name}'")
            message = f"Collection '{collection_name}' deleted successfully from {scope} scope ({deleted_count} files removed)"

        return DeleteCollectionResponse(
            message=message,
            collection_name=collection_name,
            scope=scope.value,
            documents_deleted=documents_deleted,
            chunks_deleted=chunks_deleted
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete collection: {str(e)}"
        )


@router.get("/collections/{collection_name}/documents", response_model=List[DocumentInfo])
async def list_collection_documents(
    collection_name: str,
    scope: IngestScope = Query(..., description="Collection scope: 'private' or 'shared'"),
    user: UserContext = Depends(get_current_user)
):
    """
    List all documents in a specific collection with full metadata

    Returns comprehensive document information including:
    - Document ID, title, and hash
    - File size (bytes and MB)
    - Document type (PDF, DOCX, etc.)
    - Upload timestamp and uploader information
    - Chunk count

    Requires:
    - Valid JWT token
    - Access to the specified scope (private or shared)

    Supports both original names and URL-friendly hyphenated names:
    - "bosluk denemesi" (original with spaces)
    - "bosluk-denemesi" (URL-friendly with hyphens)
    """
    logger.info(f"Listing documents in collection '{collection_name}' ({scope.value} scope)")

    # Convert scope
    data_scope = DataScope(scope.value)

    # Check access
    if data_scope == DataScope.PRIVATE and not user.data_access.own_data:
        raise HTTPException(status_code=403, detail="No access to private collections")

    if data_scope == DataScope.SHARED and not user.data_access.shared_data:
        raise HTTPException(status_code=403, detail="No access to shared collections")

    # Create temporary scope identifier for name resolution
    temp_scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=collection_name
    )

    # Resolve collection name (handles both original and hyphenated names)
    # This will raise HTTPException(404) if collection metadata not found
    try:
        original_collection_name = _resolve_collection_name(collection_name, temp_scope_id, user)
        logger.info(f"✅ Resolved collection name: '{collection_name}' -> '{original_collection_name}'")
    except HTTPException as e:
        # Collection not found - provide clear error message
        logger.warning(f"❌ Collection '{collection_name}' not found in {scope.value} scope")
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found in {scope.value} scope. Make sure the collection exists and you have access to it."
        )

    # Create scope identifier with resolved original name
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=original_collection_name
    )

    # Check if collection exists in Milvus
    milvus_collection_name = scope_id.get_collection_name(settings.EMBEDDING_DIMENSION)

    # Ensure Milvus connection exists
    milvus_manager.get_connection()
    if not utility.has_collection(milvus_collection_name):
        logger.error(f"❌ Milvus collection '{milvus_collection_name}' not found (metadata exists but Milvus collection missing)")
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{original_collection_name}' not found in {scope.value} scope"
        )

    # Get collection from Milvus (do NOT auto-create in read operations)
    collection = milvus_manager.get_collection(scope_id, auto_create=False)

    # Query all chunks to get document information
    try:
        # Query with metadata fields
        results = collection.query(
            expr="id > 0",  # INT64 primary key (changed from 'id != ""')
            output_fields=["document_id", "metadata"],
            limit=16384  # Max limit
        )

        # Group by document_id and extract metadata
        documents_dict = {}
        for result in results:
            doc_id = result["document_id"]
            if doc_id not in documents_dict:
                meta = result.get("metadata", {})
                documents_dict[doc_id] = {
                    "document_id": doc_id,
                    "title": meta.get("document_title", "Unknown"),
                    "file_hash": meta.get("file_hash", ""),
                    "created_at_ts": meta.get("created_at", 0),
                    "document_size_bytes": meta.get("document_size_bytes", 0),
                    "document_type": meta.get("document_type", "PDF"),
                    "uploaded_by": meta.get("uploaded_by", ""),
                    "uploaded_by_email": meta.get("uploaded_by_email", ""),
                    "chunks_count": 1
                }
            else:
                documents_dict[doc_id]["chunks_count"] += 1

        # Convert to DocumentInfo list
        documents: List[DocumentInfo] = []
        for doc_id, doc_data in documents_dict.items():
            # Convert timestamp to ISO format
            created_at = datetime.datetime.fromtimestamp(doc_data["created_at_ts"] / 1000).isoformat() if doc_data["created_at_ts"] else datetime.datetime.now().isoformat()

            # Calculate size in MB
            size_bytes = doc_data["document_size_bytes"]
            size_mb = round(size_bytes / (1024 * 1024), 2) if size_bytes > 0 else 0.0

            # Generate presigned URL for document download
            url = None
            try:
                client = storage.client_manager.get_client()
                bucket = scope_id.get_bucket_name()
                # Document path format: users/{user_id}/collections/{collection_name}/docs/{doc_id}/{filename}.pdf
                # We need to find the actual filename
                doc_prefix = f"{scope_id.get_object_prefix('docs')}{doc_id}/"
                objects = list(client.list_objects(bucket, prefix=doc_prefix))
                if objects:
                    # Get the first PDF file
                    for obj in objects:
                        if obj.object_name.endswith('.pdf'):
                            url = client.presigned_get_object(bucket, obj.object_name, expires=datetime.timedelta(hours=1))
                            # Replace internal endpoint with external endpoint for frontend accessibility
                            if settings.MINIO_EXTERNAL_ENDPOINT != settings.MINIO_ENDPOINT:
                                url = url.replace(settings.MINIO_ENDPOINT, settings.MINIO_EXTERNAL_ENDPOINT)
                                logger.debug(f"🔄 Replaced internal endpoint with external in preview URL")
                            break
            except Exception as e:
                logger.warning(f"Could not generate presigned URL for {doc_id}: {e}")

            documents.append(DocumentInfo(
                document_id=doc_id,
                title=doc_data["title"],
                chunks_count=doc_data["chunks_count"],
                created_at=created_at,
                file_hash=doc_data["file_hash"],
                size_bytes=size_bytes,
                size_mb=size_mb,
                document_type=doc_data["document_type"],
                uploaded_by=doc_data["uploaded_by"],
                uploaded_by_email=doc_data["uploaded_by_email"],
                collection_name=original_collection_name,  # Use original name, not hyphenated
                url=url,
                scope=scope.value,
                metadata=None
            ))

        # Sort by created_at descending
        documents.sort(key=lambda x: x.created_at, reverse=True)

        logger.info(f"Found {len(documents)} documents in collection '{original_collection_name}'")
        return documents

    except Exception as e:
        logger.error(f"Failed to list documents in collection: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )
