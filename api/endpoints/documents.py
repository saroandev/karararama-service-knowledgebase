"""
Documents management endpoints with multi-tenant scope support
"""
import datetime
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from schemas.api.responses.document import DocumentInfo
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from api.core.milvus_manager import milvus_manager
from app.core.storage import storage
from app.core.auth import UserContext, require_permission
from app.services.auth_service import get_auth_service_client
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents", response_model=List[DocumentInfo])
async def list_documents(
    scope: Optional[DataScope] = Query(None, description="Filter by scope: private, shared, or all (default: all accessible)"),
    user: UserContext = Depends(require_permission("documents", "read"))
):
    """
    List documents with multi-tenant scope filtering

    Requires:
    - Valid JWT token in Authorization header
    - User must have 'documents:read' permission

    Query Parameters:
    - scope: Filter documents by scope (private, shared, or null for all accessible)
    """
    try:
        logger.info(f"📋 Listing documents for user {user.user_id} (org: {user.organization_id})")
        logger.info(f"🎯 Scope filter: {scope or 'all accessible'}")

        # Determine which collections to query
        target_collections = []

        if scope is None or scope == DataScope.ALL:
            # Get all accessible collections
            if user.data_access.own_data:
                private_scope = ScopeIdentifier(
                    organization_id=user.organization_id,
                    scope_type=DataScope.PRIVATE,
                    user_id=user.user_id
                )
                try:
                    collection = milvus_manager.get_collection(private_scope)
                    target_collections.append({"collection": collection, "scope_label": "private"})
                except Exception as e:
                    logger.warning(f"Could not load private collection: {e}")

            if user.data_access.shared_data:
                shared_scope = ScopeIdentifier(
                    organization_id=user.organization_id,
                    scope_type=DataScope.SHARED
                )
                try:
                    collection = milvus_manager.get_collection(shared_scope)
                    target_collections.append({"collection": collection, "scope_label": "shared"})
                except Exception as e:
                    logger.warning(f"Could not load shared collection: {e}")

        elif scope == DataScope.PRIVATE:
            if not user.data_access.own_data:
                raise HTTPException(403, "No access to private data")

            private_scope = ScopeIdentifier(
                organization_id=user.organization_id,
                scope_type=DataScope.PRIVATE,
                user_id=user.user_id
            )
            collection = milvus_manager.get_collection(private_scope)
            target_collections.append({"collection": collection, "scope_label": "private"})

        elif scope == DataScope.SHARED:
            if not user.data_access.shared_data:
                raise HTTPException(403, "No access to shared data")

            shared_scope = ScopeIdentifier(
                organization_id=user.organization_id,
                scope_type=DataScope.SHARED
            )
            collection = milvus_manager.get_collection(shared_scope)
            target_collections.append({"collection": collection, "scope_label": "shared"})

        # Query all target collections and merge results
        documents = []
        for collection_info in target_collections:
            collection = collection_info["collection"]
            scope_label = collection_info["scope_label"]

            logger.info(f"🔎 Querying collection: {collection.name} ({scope_label})")

            # Get unique documents (first chunk only)
            results = collection.query(
                expr="chunk_index == 0",
                output_fields=['document_id', 'metadata']
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

                # Convert timestamp to ISO format if exists
                if created_at:
                    created_at_str = datetime.datetime.fromtimestamp(created_at / 1000).isoformat()
                else:
                    created_at_str = datetime.datetime.now().isoformat()

                # Count chunks for this document in this collection
                chunk_count = len(collection.query(
                    expr=f'document_id == "{doc_id}"',
                    output_fields=['id']
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
                    url=document_url,
                    scope=scope_label  # Add scope info
                ))

        # Report usage to auth service (list operation)
        auth_client = get_auth_service_client()
        try:
            await auth_client.consume_usage(
                user_id=user.user_id,
                service_type="rag_list_documents",
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


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    scope: DataScope = Query(..., description="Scope of the document to delete (private or shared)"),
    user: UserContext = Depends(require_permission("documents", "delete"))
):
    """
    Delete a document and all its chunks from a specific scope

    Requires:
    - Valid JWT token in Authorization header
    - User must have 'documents:delete' permission
    - Scope must be specified (private or shared)
    - Only admins can delete from shared scope
    """
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

    # Create scope identifier
    scope_id = ScopeIdentifier(
        organization_id=user.organization_id,
        scope_type=scope,
        user_id=user.user_id if scope == DataScope.PRIVATE else None
    )

    logger.info(f"🗑️  Deleting document {document_id} from {scope} scope")
    logger.info(f"👤 User: {user.user_id} (org: {user.organization_id})")

    try:
        # Get scoped Milvus collection
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

        # Try to delete from MinIO as well
        minio_deleted = False
        minio_error = None
        try:
            storage.delete_document(document_id)
            logger.info(f"Deleted document {document_id} from MinIO")
            minio_deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete from MinIO: {e}")
            minio_error = str(e)

        # Report usage to auth service (deletion operation)
        auth_client = get_auth_service_client()
        try:
            await auth_client.consume_usage(
                user_id=user.user_id,
                service_type="rag_delete",
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
            return {
                "success": True,
                "document_id": document_id,
                "document_title": doc_title,
                "deleted_chunks": len(chunks),
                "message": f"'{doc_title}' dokümanı ve {len(chunks)} chunk başarıyla silindi",
                "details": {
                    "milvus_status": "success",
                    "minio_status": "success"
                }
            }
        elif milvus_deleted and not minio_deleted:
            # Partial success - document removed from search but files remain
            return {
                "success": True,
                "document_id": document_id,
                "document_title": doc_title,
                "deleted_chunks": len(chunks),
                "message": f"'{doc_title}' dokümanı veritabanından silindi ancak dosya deposundan silinemedi",
                "warning": f"MinIO silme hatası: {minio_error}",
                "details": {
                    "milvus_status": "success",
                    "minio_status": "failed",
                    "minio_error": minio_error
                }
            }

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