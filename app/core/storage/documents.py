"""
Document storage operations
"""
import io
import json
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from minio.error import S3Error
from app.config import settings
from app.core.storage.base import BaseStorage
from app.core.storage.client import MinIOClientManager
from app.core.storage.cache import StorageCache
from app.core.storage.utils import (
    sanitize_filename,
    generate_document_id,
    prepare_metadata,
    get_cache_key
)

logger = logging.getLogger(__name__)


class DocumentStorage(BaseStorage):
    """Handles document storage operations in MinIO with scope support"""

    def __init__(self, client_manager: MinIOClientManager, cache: StorageCache):
        """
        Initialize document storage

        Args:
            client_manager: MinIO client manager
            cache: Storage cache instance
        """
        self.client_manager = client_manager
        self.cache = cache
        # Legacy bucket for backward compatibility
        self.legacy_bucket = settings.MINIO_BUCKET_DOCS

    def upload_document(self, document_id: str, file_data: bytes,
                       filename: str, metadata: Optional[Dict[str, Any]] = None,
                       scope: Any = None) -> bool:
        """
        Upload a document to storage

        Args:
            document_id: Document identifier
            file_data: File content bytes
            filename: Original filename
            metadata: Optional metadata
            scope: ScopeIdentifier for multi-tenant storage (optional)

        Returns:
            True if successful, False otherwise
        """
        return self.upload_pdf_to_raw_documents(document_id, file_data, filename, metadata, scope)

    def upload_pdf_to_raw_documents(self, document_id: str, file_data: bytes,
                                   filename: str, metadata: Optional[Dict[str, Any]] = None,
                                   scope: Any = None) -> bool:
        """
        Upload PDF to scope-aware bucket with original filename
        Uses fresh client to avoid resource deadlock issues

        Args:
            document_id: Document identifier
            file_data: PDF file bytes
            filename: Original filename to preserve
            metadata: Optional metadata dictionary
            scope: ScopeIdentifier for multi-tenant storage (optional, uses legacy if None)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"[UPLOAD_START] Starting upload for document_id: {document_id}")
        logger.info(f"[UPLOAD_START] Filename: {filename}, Size: {len(file_data)} bytes")

        try:
            # Create fresh client to avoid deadlock
            client = self.client_manager.create_fresh_client()
            logger.info(f"[CLIENT_CREATED] Fresh MinIO client created to avoid deadlock")

            # Determine bucket and prefix based on scope
            if scope:
                # Scope-aware: use organization bucket + folder structure
                raw_bucket = scope.get_bucket_name()
                object_prefix = scope.get_object_prefix("docs")
                logger.info(f"[SCOPE_AWARE] Bucket: {raw_bucket}, Prefix: {object_prefix}")
            else:
                # Legacy: use old bucket structure
                raw_bucket = self.legacy_bucket
                object_prefix = ""
                logger.info(f"[LEGACY_MODE] Using legacy bucket: {raw_bucket}")

            # Check/create bucket
            try:
                if not client.bucket_exists(raw_bucket):
                    logger.warning(f"Bucket does not exist: {raw_bucket}, creating...")
                    client.make_bucket(raw_bucket)
                    logger.info(f"Created bucket: {raw_bucket}")
            except Exception as bucket_error:
                logger.debug(f"Bucket check/create info: {bucket_error}")

            # Sanitize filename for safe storage
            sanitized_filename = sanitize_filename(filename)
            pdf_object_name = f"{object_prefix}{document_id}/{sanitized_filename}"

            # Upload PDF with retry logic
            max_retries = 3
            retry_delay = 2
            file_size = len(file_data)

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        logger.info(f"[RETRY] Attempt {attempt + 1}/{max_retries} after {retry_delay}s delay")
                        time.sleep(retry_delay)

                    # Direct upload without multipart
                    client.put_object(
                        raw_bucket,
                        pdf_object_name,
                        io.BytesIO(file_data),
                        file_size,
                        content_type="application/pdf"
                    )

                    logger.info(f"[PDF_UPLOADED] Successfully uploaded: {pdf_object_name}")
                    break

                except Exception as upload_error:
                    if attempt < max_retries - 1:
                        logger.warning(f"[RETRY_NEEDED] Attempt {attempt + 1} failed: {upload_error}")
                        continue
                    else:
                        logger.error(f"[UPLOAD_FAILED] All {max_retries} attempts failed")
                        raise

            # Upload metadata
            self._upload_document_metadata(client, raw_bucket, object_prefix, document_id, filename, file_data, metadata)

            # Invalidate cache
            self.cache.invalidate(document_id)

            logger.info(f"[UPLOAD_SUCCESS] Document upload completed for {document_id}")
            return True

        except S3Error as e:
            logger.error(f"MinIO S3Error while uploading document: {e}")
            logger.error(f"Error details - Code: {e.code}, Message: {e.message}")
            logger.error(f"Bucket: {raw_bucket}, Object: {pdf_object_name if 'pdf_object_name' in locals() else 'unknown'}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading document: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _upload_document_metadata(self, client, bucket: str, object_prefix: str,
                                 document_id: str, filename: str,
                                 file_data: bytes, additional_metadata: Optional[Dict[str, Any]] = None):
        """
        Upload document metadata as separate JSON file

        Args:
            client: MinIO client
            bucket: Bucket name
            object_prefix: Object prefix (folder path)
            document_id: Document ID
            filename: Original filename
            file_data: File content
            additional_metadata: Additional metadata
        """
        try:
            # Prepare metadata
            metadata = prepare_metadata(document_id, filename, file_data, additional_metadata)

            # Save metadata as JSON with scope-aware path
            metadata_object_name = f"{object_prefix}{document_id}/{document_id}_metadata.json"
            metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8')

            client.put_object(
                bucket,
                metadata_object_name,
                io.BytesIO(metadata_json),
                len(metadata_json),
                content_type="application/json"
            )

            logger.info(f"[METADATA_UPLOADED] Metadata uploaded: {metadata_object_name}")

        except Exception as e:
            logger.error(f"Failed to upload metadata: {e}")

    def get_document(self, document_id: str) -> Optional[bytes]:
        """
        Retrieve a document from storage

        Args:
            document_id: Document identifier

        Returns:
            Document bytes or None if not found
        """
        # Check cache first
        cache_key = get_cache_key(document_id, 'document')
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            client = self.client_manager.get_client()

            # List objects in document folder
            objects = list(client.list_objects(
                self.bucket,
                prefix=f"{document_id}/",
                recursive=False
            ))

            # Find PDF file (not metadata)
            pdf_object = None
            for obj in objects:
                if obj.object_name.endswith('.pdf'):
                    pdf_object = obj
                    break

            if not pdf_object:
                logger.warning(f"No PDF found for document {document_id}")
                return None

            # Download PDF
            response = client.get_object(self.bucket, pdf_object.object_name)
            data = response.read()

            # Cache the result
            self.cache.set(cache_key, data)

            logger.debug(f"Retrieved document {document_id}")
            return data

        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            return None

    def download_pdf(self, document_id: str, filename: str) -> bytes:
        """
        Download PDF from storage (compatibility method)

        Args:
            document_id: Document identifier
            filename: Filename (not used, for compatibility)

        Returns:
            PDF bytes
        """
        data = self.get_document(document_id)
        if data is None:
            raise Exception(f"Document {document_id} not found")
        return data

    def get_document_url(self, document_id: str, expiry_seconds: int = 3600) -> Optional[str]:
        """
        Get a presigned URL for downloading a document

        Args:
            document_id: Document identifier
            expiry_seconds: URL expiry time in seconds (default 1 hour)

        Returns:
            Presigned URL string or None if document not found
        """
        try:
            client = self.client_manager.get_client()

            # List objects in document folder
            objects = list(client.list_objects(
                self.bucket,
                prefix=f"{document_id}/",
                recursive=False
            ))

            # Find PDF file (not metadata)
            pdf_object = None
            for obj in objects:
                if obj.object_name.endswith('.pdf'):
                    pdf_object = obj
                    break

            if not pdf_object:
                logger.warning(f"No PDF found for document {document_id}")
                return None

            # Generate presigned URL
            from datetime import timedelta
            url = client.presigned_get_object(
                self.bucket,
                pdf_object.object_name,
                expires=timedelta(seconds=expiry_seconds)
            )

            logger.debug(f"Generated presigned URL for document {document_id}")
            return url

        except Exception as e:
            logger.error(f"Failed to generate URL for document {document_id}: {e}")
            return None

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and all its related files

        Args:
            document_id: Document identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            client = self.client_manager.get_client()

            # List all objects with document_id prefix
            objects = client.list_objects(
                self.bucket,
                prefix=f"{document_id}/",
                recursive=True
            )

            # Delete each object
            deleted_count = 0
            for obj in objects:
                try:
                    client.remove_object(self.bucket, obj.object_name)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting {obj.object_name}: {e}")

            # Invalidate cache
            self.cache.invalidate(document_id)

            logger.info(f"Deleted {deleted_count} objects for document {document_id}")
            return deleted_count > 0

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    def document_exists(self, document_id: str) -> bool:
        """
        Check if a document exists

        Args:
            document_id: Document identifier

        Returns:
            True if exists, False otherwise
        """
        try:
            client = self.client_manager.get_client()

            # Check if any objects exist with this prefix
            objects = client.list_objects(
                self.bucket,
                prefix=f"{document_id}/",
                max_keys=1
            )

            # If we get any object, document exists
            for _ in objects:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking document existence: {e}")
            return False

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all documents in storage

        Returns:
            List of document information dictionaries
        """
        try:
            client = self.client_manager.get_client()
            documents = {}

            # List all objects
            objects = client.list_objects(self.bucket, recursive=True)

            for obj in objects:
                # Extract document_id from path
                parts = obj.object_name.split('/')
                if len(parts) >= 2:
                    document_id = parts[0]

                    if document_id not in documents:
                        documents[document_id] = {
                            'document_id': document_id,
                            'files': [],
                            'total_size': 0,
                            'last_modified': obj.last_modified
                        }

                    documents[document_id]['files'].append(obj.object_name)
                    documents[document_id]['total_size'] += obj.size

                    # Update last_modified if this object is newer
                    if obj.last_modified > documents[document_id]['last_modified']:
                        documents[document_id]['last_modified'] = obj.last_modified

            # Convert to list and add metadata
            result = []
            for doc_id, doc_info in documents.items():
                # Try to get metadata
                metadata = self.get_document_metadata(doc_id)
                if metadata:
                    doc_info['metadata'] = metadata

                result.append(doc_info)

            logger.debug(f"Listed {len(result)} documents")
            return result

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []

    def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """
        Get metadata for a document

        Args:
            document_id: Document identifier

        Returns:
            Metadata dictionary or empty dict if not found
        """
        try:
            client = self.client_manager.get_client()

            # Try to get metadata file
            metadata_object = f"{document_id}/{document_id}_metadata.json"
            response = client.get_object(self.bucket, metadata_object)
            metadata = json.loads(response.read().decode('utf-8'))

            return metadata

        except Exception as e:
            logger.debug(f"No metadata found for document {document_id}: {e}")
            return {}