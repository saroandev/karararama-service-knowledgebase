"""
Documents management endpoints with multi-tenant scope support
"""
import datetime
import json
import logging
import httpx
from typing import List
from urllib.parse import urlparse
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse, StreamingResponse

from schemas.api.responses.document import DocumentInfo, DeleteDocumentResponse, PresignedUrlResponse
from schemas.api.requests.document import PresignedUrlRequest
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from api.core.milvus_manager import milvus_manager
from app.core.storage import storage
from app.core.auth import UserContext, require_permission, get_current_user
from app.services.auth_service import get_auth_service_client
from app.services.global_db_service import get_global_db_client
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


# ==================== Helper Functions for Presigned URL ====================

def _parse_endpoint(endpoint: str) -> tuple:
    """
    Parse endpoint string to (hostname, port) tuple

    Args:
        endpoint: Endpoint string (e.g., "localhost:9000", "minio-prod.onedocs.com:443")

    Returns:
        Tuple of (hostname, port)

    Examples:
        "localhost:9000" → ("localhost", 9000)
        "minio-prod.onedocs.com:443" → ("minio-prod.onedocs.com", 443)
        "minio" → ("minio", 9000)  # Default port
    """
    if ":" in endpoint:
        host, port_str = endpoint.split(":", 1)
        return host, int(port_str)
    else:
        return endpoint, 9000  # Default MinIO port


def _is_collection_document(url: str) -> bool:
    """
    Check if document is from collection (MinIO) or external source

    Uses environment variables to determine source type:
    - MINIO_ENDPOINT: Collection MinIO (user documents)
    - GLOBAL_DB_MINIO_ENDPOINT: External source MinIO (MEVZUAT/KARAR)

    Args:
        url: Full document URL (to check both hostname and port)

    Returns:
        True if collection document, False if external source

    Examples:
        # Development
        "http://localhost:9000/..." → True (collection)
        "http://localhost:9040/..." → False (external)

        # Production
        "https://minio-kb.onedocs.com/..." → True (collection)
        "https://minio-globaldb.onedocs.com/..." → False (external)
    """
    parsed = urlparse(url)

    # Get hostname and port from URL
    hostname = parsed.hostname or ""
    port = parsed.port

    # Collection MinIO endpoint (from config)
    collection_host, collection_port = _parse_endpoint(settings.MINIO_ENDPOINT)

    # Check if hostname + port matches collection MinIO
    # Case 1: Exact match with collection endpoint
    if hostname == collection_host and port == collection_port:
        return True

    # Case 2: Special case for "minio" hostname (Docker internal)
    if hostname == "minio" and (port == 9000 or port is None):
        return True

    # Otherwise, it's an external source
    return False


def _extract_minio_path(url: str) -> tuple:
    """
    Extract bucket and object_key from MinIO URL

    Args:
        url: Full MinIO URL

    Returns:
        Tuple of (bucket_name, object_key)

    Example:
        Input: http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf?X-Amz-...
        Output: ("org-abc", "users/xyz/docs/doc-123/file.pdf")
    """
    parsed = urlparse(url)
    # Remove query parameters and leading slash
    path = parsed.path.lstrip("/").split("?")[0]
    path_parts = path.split("/")

    if len(path_parts) < 2:
        raise ValueError(f"Invalid MinIO URL format: {url}")

    bucket = path_parts[0]
    object_key = "/".join(path_parts[1:])

    return bucket, object_key


def _extract_document_id_from_url(url: str) -> str:
    """
    Extract document_id from URL path

    Args:
        url: Document URL

    Returns:
        Document ID

    Example:
        Input: /users/xyz/docs/doc-123/file.pdf
        Output: doc-123
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]  # Remove empty parts

    # Find "docs" folder and get next part (document_id)
    if "docs" in path_parts:
        docs_idx = path_parts.index("docs")
        if docs_idx + 1 < len(path_parts):
            return path_parts[docs_idx + 1]

    raise ValueError(f"Cannot extract document_id from URL: {url}")


# ==================== Presigned URL Endpoint ====================

@router.post("/docs/presign", response_model=PresignedUrlResponse)
async def get_presigned_url_for_viewing(
    request: PresignedUrlRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Generate presigned URL for inline document viewing

    **Supports two scenarios:**
    1. **Collection Documents**: Documents stored in local MinIO (user's own documents)
       - Generates presigned URL directly from MinIO
    2. **External Sources**: Documents from Global DB service (MEVZUAT/KARAR)
       - Forwards request to Global DB service to get presigned URL

    **URL Detection:**
    - Collection documents have hostname: `minio`, `localhost`, or configured MINIO_ENDPOINT
    - External sources have different hostnames (global-db MinIO instance)

    **Authentication:**
    - Requires valid JWT token in Authorization header

    **Example Request:**
    ```json
    {
      "document_url": "http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf?X-Amz-...",
      "expires_seconds": 3600
    }
    ```

    **Response:**
    - URL with inline display headers (opens in browser instead of downloading)
    - `source_type`: "collection" or "external"
    """
    try:
        logger.info(f"🔗 Presigned URL request from user {user.user_id}")
        logger.info(f"📄 Document URL: {request.document_url[:100]}...")

        # Determine source type based on hostname + port
        is_collection = _is_collection_document(request.document_url)

        if is_collection:
            # ==================== SCENARIO 1: Collection Document ====================
            logger.info("📦 Detected collection document (local MinIO)")

            try:
                # Extract bucket and object_key from URL
                bucket, object_key = _extract_minio_path(request.document_url)
                logger.info(f"  Bucket: {bucket}")
                logger.info(f"  Object key: {object_key}")

                # Extract document_id for response
                document_id = _extract_document_id_from_url(request.document_url)

                # Generate presigned URL with inline display headers
                client = storage.client_manager.get_client()
                presigned_url = client.presigned_get_object(
                    bucket,
                    object_key,
                    expires=timedelta(seconds=request.expires_seconds),
                    response_headers={
                        "response-content-type": "application/pdf",
                        "response-content-disposition": "inline"
                    }
                )

                # Replace internal endpoint with external endpoint for frontend accessibility
                if settings.MINIO_EXTERNAL_ENDPOINT != settings.MINIO_ENDPOINT:
                    presigned_url = presigned_url.replace(settings.MINIO_ENDPOINT, settings.MINIO_EXTERNAL_ENDPOINT)
                    logger.debug(f"🔄 Replaced internal endpoint with external: {settings.MINIO_ENDPOINT} → {settings.MINIO_EXTERNAL_ENDPOINT}")

                logger.info(f"✅ Generated presigned URL for collection document {document_id}")

                return PresignedUrlResponse(
                    url=presigned_url,
                    expires_in=request.expires_seconds,
                    document_id=document_id,
                    source_type="collection"
                )

            except ValueError as e:
                logger.error(f"❌ Invalid URL format: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": {
                            "code": "INVALID_URL_FORMAT",
                            "message": "Geçersiz doküman URL formatı",
                            "details": str(e)
                        }
                    }
                )

            except Exception as e:
                logger.error(f"❌ MinIO presign error: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "success": False,
                        "error": {
                            "code": "MINIO_PRESIGN_FAILED",
                            "message": "Presigned URL oluşturulamadı",
                            "details": str(e)
                        }
                    }
                )

        else:
            # ==================== SCENARIO 2: External Source ====================
            logger.info("🌍 Detected external source document (Global DB)")

            try:
                # Call Global DB Service to get presigned URL
                # Global DB handles URL parsing and MinIO presigned URL generation
                global_db_client = get_global_db_client()

                # Get user's access token from UserContext
                user_token = user.raw_token if hasattr(user, 'raw_token') else ""

                if not user_token:
                    logger.error("❌ User token not available for Global DB request")
                    raise HTTPException(
                        status_code=401,
                        detail={
                            "success": False,
                            "error": {
                                "code": "TOKEN_UNAVAILABLE",
                                "message": "Authentication token gerekli",
                                "details": "Global DB erişimi için token bulunamadı"
                            }
                        }
                    )

                # Forward presign request to Global DB Service
                result = await global_db_client.get_presigned_url_from_external(
                    document_url=request.document_url,  # Send full URL
                    user_token=user_token,
                    expires_seconds=request.expires_seconds
                )

                # Check if Global DB request failed
                if not result.get("url"):
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"❌ Global DB presign failed: {error_msg}")

                    # Determine appropriate HTTP status code
                    if "not found" in error_msg.lower():
                        status_code = 404
                        error_code = "DOCUMENT_NOT_FOUND"
                    elif "auth" in error_msg.lower():
                        status_code = 401
                        error_code = "AUTHENTICATION_FAILED"
                    elif "bad request" in error_msg.lower():
                        status_code = 400
                        error_code = "INVALID_URL_FORMAT"
                    else:
                        status_code = 500
                        error_code = "EXTERNAL_SERVICE_ERROR"

                    raise HTTPException(
                        status_code=status_code,
                        detail={
                            "success": False,
                            "error": {
                                "code": error_code,
                                "message": "External source'dan presigned URL alınamadı",
                                "details": error_msg
                            }
                        }
                    )

                logger.info(f"✅ Received presigned URL from Global DB")

                return PresignedUrlResponse(
                    url=result["url"],
                    expires_in=result.get("expires_in", request.expires_seconds),
                    document_id=result.get("document_id", "unknown"),
                    source_type=result.get("source_type", "external")
                )

            except HTTPException:
                # Re-raise HTTP exceptions
                raise

            except Exception as e:
                logger.error(f"❌ External presign error: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "success": False,
                        "error": {
                            "code": "EXTERNAL_PRESIGN_FAILED",
                            "message": "External source'dan presigned URL alınamadı",
                            "details": str(e)
                        }
                    }
                )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"❌ Unexpected error in presign endpoint: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Beklenmeyen bir hata oluştu",
                    "details": str(e)
                }
            }
        )


# ==================== Preview Proxy Endpoint (CORS-safe) ====================

@router.get("/docs/preview")
async def preview_document_proxy(
    document_url: str = Query(..., description="Full document URL from MinIO or external source"),
    user: UserContext = Depends(get_current_user)
):
    """
    Preview document through backend proxy (CORS-safe solution)

    This endpoint solves CORS issues by streaming the document through the backend
    instead of having the frontend make direct requests to MinIO.

    **How it works:**
    1. Generates presigned URL using existing presign logic
    2. Fetches document from MinIO on the backend
    3. Streams it to frontend with proper CORS headers (FastAPI middleware handles this)

    **Authentication:**
    - Requires valid JWT token in Authorization header

    **Example Request:**
    ```
    GET /docs/preview?document_url=http://minio-api-preprod.onedocs.ai/mevzuat/...
    Authorization: Bearer <token>
    ```

    **Response:**
    - Content-Type: application/pdf
    - Content-Disposition: inline (opens in browser)
    - CORS headers: Automatically added by FastAPI middleware

    **Frontend Usage:**
    ```javascript
    const previewUrl = `${API_BASE_URL}/docs/preview?document_url=${encodeURIComponent(documentUrl)}`;
    <iframe src={previewUrl} />
    ```
    """
    try:
        logger.info(f"📺 Preview proxy request from user {user.user_id}")
        logger.info(f"📄 Document URL: {document_url[:100]}...")

        # Step 1: Generate presigned URL using existing logic
        request = PresignedUrlRequest(
            document_url=document_url,
            expires_seconds=3600  # 1 hour
        )

        presigned_response = await get_presigned_url_for_viewing(request, user)
        presigned_url = presigned_response.url

        logger.info(f"✅ Generated presigned URL, fetching document from MinIO...")

        # Step 2: Fetch document from MinIO
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(presigned_url)

            if response.status_code != 200:
                logger.error(f"❌ MinIO returned status {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail={
                        "success": False,
                        "error": {
                            "code": "DOCUMENT_FETCH_FAILED",
                            "message": "Doküman alınamadı",
                            "details": f"MinIO status: {response.status_code}"
                        }
                    }
                )

            # Get content type from response (usually application/pdf)
            content_type = response.headers.get("content-type", "application/pdf")
            content_length = response.headers.get("content-length")

            logger.info(f"✅ Document fetched successfully ({content_length} bytes)")

            # Step 3: Stream to frontend with proper headers
            headers = {
                "Content-Disposition": "inline",  # Open in browser, not download
                "Content-Type": content_type,
            }

            if content_length:
                headers["Content-Length"] = content_length

            # FastAPI CORS middleware will automatically add:
            # - Access-Control-Allow-Origin
            # - Access-Control-Allow-Credentials
            # - Access-Control-Allow-Methods
            # - Access-Control-Allow-Headers

            return StreamingResponse(
                iter([response.content]),
                media_type=content_type,
                headers=headers
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"❌ Preview proxy error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": {
                    "code": "PREVIEW_PROXY_FAILED",
                    "message": "Doküman önizlemesi başarısız",
                    "details": str(e)
                }
            }
        )