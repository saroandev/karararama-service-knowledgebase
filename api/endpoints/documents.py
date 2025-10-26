"""
Documents management endpoints with multi-tenant scope support
"""
import datetime
import json
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse

from schemas.api.responses.document import DocumentInfo, DeleteDocumentResponse
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from api.core.milvus_manager import milvus_manager
from app.core.storage import storage
from app.core.auth import UserContext, require_permission, get_current_user
from app.services.auth_service import get_auth_service_client
from app.config import settings
from app.config.constants import ServiceType

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/collections/{collection_name}/documents", response_model=List[DocumentInfo])
async def list_documents(
    collection_name: str,
    scope: DataScope = Query(
        ...,
        description="REQUIRED: Scope filter - 'private' (your documents), 'shared' (organization documents), or 'all' (both private and shared)"
    ),
    user: UserContext = Depends(get_current_user)  # Only JWT token required
):
    """
    List documents from a specific collection with scope filtering

    Requires:
    - Valid JWT token in Authorization header
    - **collection_name in URL path is REQUIRED** (e.g., /collections/test_duzgun/documents)
    - **scope query parameter is REQUIRED** (must be explicitly specified)

    URL Parameters:
    - **collection_name (REQUIRED)**: Collection name to list documents from
      - Examples: "sozlesmeler", "kanunlar", "test_duzgun"
      - Specified in URL path

    Query Parameters:
    - **scope (REQUIRED)**: Filter documents by scope
      - **private**: Only your personal documents
      - **shared**: Only organization shared documents
      - **all**: Both private and shared documents
      - Returns 422 Unprocessable Entity if not provided

    Example URLs:
    - GET /collections/test_duzgun/documents?scope=private
    - GET /collections/sozlesmeler/documents?scope=shared
    - GET /collections/kanunlar/documents?scope=all

    This RESTful approach makes the collection hierarchy clear and explicit.
    """
    # Rename the path parameter to match the rest of the function
    collection = collection_name
    try:
        logger.info(f"📋 Listing documents for user {user.user_id} (org: {user.organization_id})")
        logger.info(f"🎯 Scope: {scope}, Collection: {collection}")

        # Determine which collections to query based on explicit scope
        target_collections = []

        if scope == DataScope.ALL:
            # Get all accessible collections
            if user.data_access.own_data:
                private_scope = ScopeIdentifier(
                    organization_id=user.organization_id,
                    scope_type=DataScope.PRIVATE,
                    user_id=user.user_id,
                    collection_name=collection  # Add collection filter
                )
                try:
                    milvus_collection = milvus_manager.get_collection(private_scope)
                    scope_label = f"private/{collection}"
                    target_collections.append({"collection": milvus_collection, "scope_label": scope_label})
                except Exception as e:
                    logger.warning(f"Could not load private collection: {e}")

            if user.data_access.shared_data:
                shared_scope = ScopeIdentifier(
                    organization_id=user.organization_id,
                    scope_type=DataScope.SHARED,
                    collection_name=collection  # Add collection filter
                )
                try:
                    milvus_collection = milvus_manager.get_collection(shared_scope)
                    scope_label = f"shared/{collection}"
                    target_collections.append({"collection": milvus_collection, "scope_label": scope_label})
                except Exception as e:
                    logger.warning(f"Could not load shared collection: {e}")

        elif scope == DataScope.PRIVATE:
            if not user.data_access.own_data:
                raise HTTPException(403, "No access to private data")

            private_scope = ScopeIdentifier(
                organization_id=user.organization_id,
                scope_type=DataScope.PRIVATE,
                user_id=user.user_id,
                collection_name=collection  # Collection is required
            )
            milvus_collection = milvus_manager.get_collection(private_scope)
            scope_label = f"private/{collection}"
            target_collections.append({"collection": milvus_collection, "scope_label": scope_label})

        elif scope == DataScope.SHARED:
            if not user.data_access.shared_data:
                raise HTTPException(403, "No access to shared data")

            shared_scope = ScopeIdentifier(
                organization_id=user.organization_id,
                scope_type=DataScope.SHARED,
                collection_name=collection  # Collection is required
            )
            milvus_collection = milvus_manager.get_collection(shared_scope)
            scope_label = f"shared/{collection}"
            target_collections.append({"collection": milvus_collection, "scope_label": scope_label})

        # Query all target collections and merge results
        documents = []
        for collection_info in target_collections:
            collection = collection_info["collection"]
            scope_label = collection_info["scope_label"]

            logger.info(f"🔎 Querying collection: {collection.name} ({scope_label})")

            # Get unique documents (first chunk only)
            results = collection.query(
                expr="chunk_index == 0",
                output_fields=['document_id', 'metadata'],
                limit=16384  # Milvus maximum limit
            )

            logger.info(f"✅ Found {len(results)} documents in {scope_label}")

            for result in results:
                doc_id = result.get('document_id')
                metadata = result.get('metadata')

                # Parse metadata
                if isinstance(metadata, str):
                    meta_dict = json.loads(metadata)
                else:
                    meta_dict = metadata if metadata else {}

                doc_title = meta_dict.get('document_title', 'Unknown')
                file_hash = meta_dict.get('file_hash', '')
                created_at = meta_dict.get('created_at', 0)
                document_size_bytes = meta_dict.get('document_size_bytes', 0)
                document_type = meta_dict.get('document_type', 'PDF')
                uploaded_by = meta_dict.get('uploaded_by', '')
                uploaded_by_email = meta_dict.get('uploaded_by_email', '')
                collection_name_meta = meta_dict.get('collection_name', None)

                # Convert timestamp to ISO format if exists
                if created_at:
                    created_at_str = datetime.datetime.fromtimestamp(created_at / 1000).isoformat()
                else:
                    created_at_str = datetime.datetime.now().isoformat()

                # Calculate size in MB
                size_mb = round(document_size_bytes / (1024 * 1024), 2) if document_size_bytes > 0 else 0.0

                # Count chunks for this document in this collection
                chunk_count = len(collection.query(
                    expr=f'document_id == "{doc_id}"',
                    output_fields=['id'],
                    limit=16384  # Milvus maximum limit
                ))

                # Try to get MinIO URL for the document
                document_url = None
                try:
                    document_url = storage.documents.get_document_url(doc_id)
                except Exception as url_error:
                    logger.debug(f"Could not generate URL for document {doc_id}: {url_error}")

                documents.append(DocumentInfo(
                    document_id=doc_id,
                    title=doc_title,
                    chunks_count=chunk_count,
                    created_at=created_at_str,
                    file_hash=file_hash,
                    size_bytes=document_size_bytes,
                    size_mb=size_mb,
                    document_type=document_type,
                    uploaded_by=uploaded_by,
                    uploaded_by_email=uploaded_by_email,
                    collection_name=collection_name_meta,
                    url=document_url,
                    scope=scope_label,  # Add scope info
                    metadata=meta_dict
                ))

        # Report usage to auth service (list operation)
        auth_client = get_auth_service_client()
        try:
            await auth_client.consume_usage(
                user_id=user.user_id,
                service_type=ServiceType.LIST_DOCUMENTS,
                tokens_used=0,  # No tokens for list operation
                processing_time=0,
                metadata={
                    "documents_count": len(documents)
                }
            )
        except Exception as e:
            # Log but don't fail the request
            logger.warning(f"Failed to report usage to auth service: {str(e)}")

        return documents

    except Exception as e:
        logger.error(f"List documents error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.delete("/collections/{collection_name}/documents/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    collection_name: str,
    document_id: str,
    scope: DataScope = Query(..., description="Scope of the document to delete (private or shared)"),
    user: UserContext = Depends(get_current_user)  # Only JWT token required
):
    """
    Delete a document and all its chunks from a specific collection and scope

    Requires:
    - Valid JWT token in Authorization header
    - **collection_name in URL path is REQUIRED**
    - Scope must be specified (private or shared)
    - Users can delete from their PRIVATE scope
    - Only ADMIN role can delete from SHARED scope

    URL Parameters:
    - **collection_name (REQUIRED)**: Collection name to delete from
      - Examples: "sozlesmeler", "test_duzgun", "kanunlar"
      - Specified in URL path
    - **document_id (REQUIRED)**: The document ID to delete

    Query Parameters:
    - **scope (REQUIRED)**: Scope of the document (private or shared)

    Example URLs:
    - DELETE /collections/test_duzgun/documents/doc-123?scope=private
    - DELETE /collections/sozlesmeler/documents/doc-456?scope=shared
    """
    # Use the path parameter as collection
    collection = collection_name
    # Validate scope permissions
    if scope == DataScope.SHARED and user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "İzin reddedildi",
                    "details": "Sadece adminler shared scope'tan silme yapabilir"
                }
            }
        )

    if scope == DataScope.ALL:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_SCOPE",
                    "message": "Geçersiz scope",
                    "details": "Silme işlemi için 'private' veya 'shared' scope belirtilmelidir"
                }
            }
        )
    # Validate document ID format
    if not document_id or not document_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_DOCUMENT_ID",
                    "message": "Geçersiz doküman ID'si",
                    "details": "Doküman ID'si boş olamaz"
                }
            }
        )

    # Create scope identifier with optional collection
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=scope,
        user_id=user.user_id if scope == DataScope.PRIVATE else None,
        collection_name=collection  # Add collection filter
    )

    collection_label = f" from collection '{collection}'" if collection else " from default space"
    logger.info(f"🗑️  Deleting document {document_id} from {scope} scope{collection_label}")
    logger.info(f"👤 User: {user.user_id} (org: {user.organization_id})")

    try:
        # Get scoped Milvus collection (do NOT auto-create for delete operation)
        try:
            collection = milvus_manager.get_collection(scope_id)
        except Exception as e:
            logger.error(f"Milvus connection error: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Veritabanı bağlantısı kurulamadı",
                        "details": f"Milvus servisine erişilemiyor: {str(e)}"
                    }
                }
            )

        # Find document chunks
        chunks = collection.query(
            expr=f'document_id == "{document_id}"',
            output_fields=['id', 'metadata']
        )

        if not chunks:
            logger.info(f"Document not found: {document_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": {
                        "code": "DOCUMENT_NOT_FOUND",
                        "message": "Doküman bulunamadı",
                        "details": f"'{document_id}' ID'sine sahip doküman mevcut değil"
                    }
                }
            )

        # Get document metadata for response
        doc_metadata = chunks[0].get('metadata', {})
        if isinstance(doc_metadata, str):
            import json
            doc_metadata = json.loads(doc_metadata)
        doc_title = doc_metadata.get('document_title', 'Unknown')

        # Delete chunks from Milvus
        ids_to_delete = [chunk['id'] for chunk in chunks]
        try:
            collection.delete(expr=f"id in {ids_to_delete}")
            logger.info(f"Deleted {len(chunks)} chunks from Milvus for document {document_id}")
            milvus_deleted = True
        except Exception as e:
            logger.error(f"Failed to delete from Milvus: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": {
                        "code": "MILVUS_DELETE_FAILED",
                        "message": "Veritabanından silme işlemi başarısız",
                        "details": f"Milvus silme hatası: {str(e)}"
                    }
                }
            )

        # Try to delete from MinIO as well (scope-aware)
        minio_deleted = False
        minio_error = None
        try:
            storage.delete_document(document_id, scope_id)
            logger.info(f"Deleted document {document_id} from MinIO (scope: {scope})")
            minio_deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete from MinIO: {e}")
            minio_error = str(e)

        # Report usage to auth service (deletion operation)
        auth_client = get_auth_service_client()
        try:
            await auth_client.consume_usage(
                user_id=user.user_id,
                service_type=ServiceType.DELETE_DOCUMENT,
                tokens_used=0,  # No tokens for delete operation
                processing_time=0,
                metadata={
                    "document_id": document_id,
                    "document_title": doc_title,
                    "chunks_deleted": len(chunks)
                }
            )
        except Exception as e:
            # Log but don't fail the request
            logger.warning(f"Failed to report usage to auth service: {str(e)}")

        # Prepare response based on deletion results
        if milvus_deleted and minio_deleted:
            response_data = DeleteDocumentResponse(
                success=True,
                document_id=document_id,
                document_title=doc_title,
                deleted_chunks=len(chunks),
                message=f"'{doc_title}' dokümanı ve {len(chunks)} chunk başarıyla silindi",
                details={
                    "milvus_status": "success",
                    "minio_status": "success"
                }
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=response_data.model_dump()
            )

        elif milvus_deleted and not minio_deleted:
            # Partial success - document removed from search but files remain
            response_data = DeleteDocumentResponse(
                success=True,
                document_id=document_id,
                document_title=doc_title,
                deleted_chunks=len(chunks),
                message=f"'{doc_title}' dokümanı veritabanından silindi ancak dosya deposundan silinemedi",
                warning=f"MinIO silme hatası: {minio_error}",
                details={
                    "milvus_status": "success",
                    "minio_status": "failed"
                }
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=response_data.model_dump()
            )

    except HTTPException:
        # Re-raise HTTP exceptions with our custom format
        raise
    except Exception as e:
        logger.error(f"Unexpected delete document error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Beklenmeyen bir hata oluştu",
                    "details": f"Silme işlemi sırasında hata: {str(e)}"
                }
            }
        )