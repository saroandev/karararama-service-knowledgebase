"""
Collection management endpoints

Provides CRUD operations for organizing documents into collections.
Collections are namespaces within a scope (private/shared) for better organization.
"""

import logging
import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from schemas.api.requests.collection import CreateCollectionRequest, UpdateCollectionRequest
from schemas.api.requests.scope import DataScope, IngestScope, ScopeIdentifier
from schemas.api.responses.collection import (
    CreateCollectionResponse,
    ListCollectionsResponse,
    DeleteCollectionResponse,
    CollectionInfo
)
from api.core.milvus_manager import milvus_manager
from app.core.auth import UserContext, get_current_user
from app.core.storage import storage
from app.config import settings
from pymilvus import utility

logger = logging.getLogger(__name__)
router = APIRouter()


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

    # Check if collection exists in Milvus
    if not utility.has_collection(milvus_collection_name):
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' not found in {scope_id.scope_type.value} scope"
        )

    # Get collection from Milvus
    collection = milvus_manager.get_collection(scope_id)

    # Get statistics
    try:
        stats = collection.query(
            expr="id != ''",
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

    except Exception:
        # No metadata file exists yet
        pass

    return CollectionInfo(
        name=collection_name,
        scope=scope_id.scope_type.value,
        description=description,
        document_count=document_count,
        chunk_count=chunk_count,
        created_at=created_at,
        size_bytes=size_bytes,
        metadata=metadata,
        milvus_collection_name=milvus_collection_name,
        minio_prefix=minio_prefix
    )


@router.post("/collections", response_model=CreateCollectionResponse)
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
    if utility.has_collection(collection_name):
        raise HTTPException(
            status_code=409,
            detail=f"Collection '{request.name}' already exists in {request.scope} scope"
        )

    try:
        # Create Milvus collection
        milvus_manager.get_collection(scope_id)
        logger.info(f"Created Milvus collection: {collection_name}")

        # Save metadata to MinIO
        metadata_content = {
            "collection_name": request.name,
            "scope": request.scope.value,
            "description": request.description,
            "metadata": request.metadata,
            "created_at": datetime.datetime.now().isoformat(),
            "created_by": user.user_id,
            "organization_id": user.organization_id
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

        # Get collection info
        collection_info = _get_collection_info(request.name, scope_id, user)

        return CreateCollectionResponse(
            message=f"Collection '{request.name}' created successfully in {request.scope} scope",
            collection=collection_info
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

    # Get all Milvus collections
    all_collections = utility.list_collections()

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
    """
    logger.info(f"Getting collection '{collection_name}' in {scope} scope")

    # Convert scope
    data_scope = DataScope(scope.value)

    # Create scope identifier
    scope_id = ScopeIdentifier(
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

    return _get_collection_info(collection_name, scope_id, user)


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
    """
    logger.info(f"Deleting collection '{collection_name}' in {scope} scope")

    # Check permissions
    _check_collection_permission(user, scope, "delete")

    # Convert scope
    data_scope = DataScope(scope.value)

    # Create scope identifier
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=data_scope,
        user_id=user.user_id if scope == IngestScope.PRIVATE else None,
        collection_name=collection_name
    )

    # Get collection info before deleting
    try:
        collection_info = _get_collection_info(collection_name, scope_id, user)
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
        if utility.has_collection(collection_name_milvus):
            from pymilvus import Collection
            collection = Collection(collection_name_milvus)
            collection.drop()
            logger.info(f"Dropped Milvus collection: {collection_name_milvus}")

        # Delete from MinIO
        client = storage.client_manager.get_client()
        bucket = scope_id.get_bucket_name()
        collection_prefix = scope_id.get_object_prefix("docs").rstrip("/")  # Remove trailing slash

        # List and delete all objects with collection prefix
        objects_to_delete = client.list_objects(bucket, prefix=collection_prefix, recursive=True)

        deleted_count = 0
        for obj in objects_to_delete:
            try:
                client.remove_object(bucket, obj.object_name)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting object {obj.object_name}: {e}")

        logger.info(f"Deleted {deleted_count} objects from MinIO for collection '{collection_name}'")

        return DeleteCollectionResponse(
            message=f"Collection '{collection_name}' deleted successfully from {scope} scope",
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
