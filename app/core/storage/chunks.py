"""
Chunk storage operations
"""
import io
import json
import logging
from typing import Optional, List, Dict, Any
from minio.error import S3Error
from app.config import settings
from app.core.storage.base import BaseChunkStorage
from app.core.storage.client import MinIOClientManager
from app.core.storage.cache import StorageCache
from app.core.storage.utils import get_cache_key

logger = logging.getLogger(__name__)


class ChunkStorage(BaseChunkStorage):
    """Handles chunk storage operations in MinIO with scope support"""

    def __init__(self, client_manager: MinIOClientManager, cache: StorageCache):
        """
        Initialize chunk storage

        Args:
            client_manager: MinIO client manager
            cache: Storage cache instance
        """
        self.client_manager = client_manager
        self.cache = cache
        # Legacy bucket for backward compatibility
        self.legacy_bucket = settings.MINIO_BUCKET_CHUNKS

    def upload_chunk(self, document_id: str, chunk_id: str,
                    chunk_text: str, metadata: Optional[Dict[str, Any]] = None,
                    scope: Any = None) -> bool:
        """
        Upload a single text chunk to MinIO

        Args:
            document_id: Document identifier
            chunk_id: Unique chunk identifier
            chunk_text: Chunk text content
            metadata: Optional metadata
            scope: ScopeIdentifier for multi-tenant storage (optional, uses legacy if None)

        Returns:
            True if successful, False otherwise
        """
        try:
            client = self.client_manager.get_client()

            # Determine bucket and prefix based on scope
            if scope:
                # Scope-aware: use organization bucket + folder structure
                bucket = scope.get_bucket_name()
                object_prefix = scope.get_object_prefix("chunks")
                logger.debug(f"[SCOPE_AWARE] Bucket: {bucket}, Prefix: {object_prefix}")
            else:
                # Legacy: use old bucket structure
                bucket = self.legacy_bucket
                object_prefix = ""
                logger.debug(f"[LEGACY_MODE] Using legacy bucket: {bucket}")

            # Prepare chunk data
            chunk_data = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "text": chunk_text,
                "metadata": metadata or {}
            }

            # Convert to JSON
            chunk_json = json.dumps(chunk_data, ensure_ascii=False, indent=2)
            chunk_bytes = chunk_json.encode('utf-8')

            # Object name with scope-aware path
            object_name = f"{object_prefix}{document_id}/{chunk_id}.json"

            # Upload to MinIO
            client.put_object(
                bucket,
                object_name,
                io.BytesIO(chunk_bytes),
                len(chunk_bytes),
                content_type='application/json'
            )

            # Invalidate cache for this document
            self.cache.invalidate(document_id)

            logger.debug(f"Uploaded chunk {chunk_id} for document {document_id}")
            return True

        except S3Error as e:
            logger.error(f"Failed to upload chunk {chunk_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading chunk: {e}")
            return False

    def upload_chunks(self, chunks: List[Dict[str, Any]], document_id: str,
                     scope: Any = None) -> bool:
        """
        Upload multiple chunks in batch

        Args:
            chunks: List of chunk dictionaries
            document_id: Document identifier
            scope: ScopeIdentifier for multi-tenant storage (optional)

        Returns:
            True if all successful, False otherwise
        """
        success_count = 0

        for chunk in chunks:
            chunk_id = chunk.get('chunk_id')
            chunk_text = chunk.get('text', '')
            metadata = chunk.get('metadata', {})

            if self.upload_chunk(document_id, chunk_id, chunk_text, metadata, scope):
                success_count += 1
            else:
                logger.warning(f"Failed to upload chunk {chunk_id}")

        logger.info(f"Uploaded {success_count}/{len(chunks)} chunks for document {document_id}")
        return success_count == len(chunks)

    def save_chunks_batch(self, document_id: str, chunks_data: List[Dict[str, Any]]) -> List[str]:
        """
        Save multiple chunks in batch (compatibility method)

        Args:
            document_id: Document identifier
            chunks_data: List of chunk data dictionaries

        Returns:
            List of object paths
        """
        paths = []
        for chunk in chunks_data:
            chunk_id = chunk.get('chunk_id', chunk.get('id', ''))
            if self.upload_chunk(document_id, chunk_id, chunk.get('text', ''), chunk.get('metadata')):
                paths.append(f"{document_id}/{chunk_id}.json")
        return paths

    def get_chunks(self, document_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all chunks for a document

        Args:
            document_id: Document identifier

        Returns:
            List of chunk dictionaries or None if error
        """
        # Check cache first
        cache_key = get_cache_key(document_id, 'chunks')
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            client = self.client_manager.get_client()
            chunks = []

            # List all objects with document_id prefix
            objects = client.list_objects(
                self.bucket,
                prefix=f"{document_id}/",
                recursive=True
            )

            for obj in objects:
                try:
                    # Get chunk data
                    response = client.get_object(self.bucket, obj.object_name)
                    chunk_data = json.loads(response.read().decode('utf-8'))
                    chunks.append(chunk_data)
                except Exception as e:
                    logger.error(f"Error reading chunk {obj.object_name}: {e}")

            # Sort chunks by chunk_id
            chunks.sort(key=lambda x: x.get('chunk_id', ''))

            # Cache the result
            self.cache.set(cache_key, chunks)

            logger.debug(f"Retrieved {len(chunks)} chunks for document {document_id}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to get chunks for document {document_id}: {e}")
            return None

    def delete_chunks(self, document_id: str) -> bool:
        """
        Delete all chunks for a document

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
                    logger.error(f"Error deleting chunk {obj.object_name}: {e}")

            # Invalidate cache
            self.cache.invalidate(document_id)

            logger.info(f"Deleted {deleted_count} chunks for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete chunks for document {document_id}: {e}")
            return False