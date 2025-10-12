"""
Storage module - Modular storage implementation with backward compatibility
"""
import logging
from typing import Optional, List, Dict, Any
from app.core.storage.client import MinIOClientManager
from app.core.storage.cache import StorageCache
from app.core.storage.documents import DocumentStorage
from app.core.storage.chunks import ChunkStorage

logger = logging.getLogger(__name__)


class Storage:
    """
    Main storage facade that provides unified interface for all storage operations
    Maintains backward compatibility with old storage.py
    """

    def __init__(self):
        """Initialize storage components"""
        # Initialize shared components
        self.client_manager = MinIOClientManager()
        self.cache = StorageCache()

        # Initialize storage modules
        self.documents = DocumentStorage(self.client_manager, self.cache)
        self.chunks = ChunkStorage(self.client_manager, self.cache)

        # For backward compatibility - expose client
        self.client = self.client_manager.get_client()

        logger.info("Storage module initialized with modular architecture")

    # === Document Operations (backward compatibility) ===

    def upload_pdf_to_raw_documents(self, document_id: str, file_data: bytes,
                                   filename: str, metadata: Optional[Dict[str, Any]] = None,
                                   scope: Any = None) -> bool:
        """Upload PDF to scope-aware bucket"""
        return self.documents.upload_pdf_to_raw_documents(document_id, file_data, filename, metadata, scope)

    def get_document(self, document_id: str) -> Optional[bytes]:
        """Get document from storage"""
        return self.documents.get_document(document_id)

    def download_pdf(self, document_id: str, filename: str) -> bytes:
        """Download PDF from storage (compatibility)"""
        return self.documents.download_pdf(document_id, filename)

    def delete_document(self, document_id: str, scope: Any = None) -> bool:
        """
        Delete document and all related files from scope-aware storage

        Args:
            document_id: Document identifier
            scope: ScopeIdentifier for multi-tenant storage (optional, uses legacy if None)

        Returns:
            True if successful, False otherwise
        """
        # Delete document files (PDF and metadata)
        doc_deleted = self.documents.delete_document(document_id, scope)
        # Delete chunks
        chunks_deleted = self.chunks.delete_chunks(document_id, scope)
        return doc_deleted and chunks_deleted

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents"""
        return self.documents.list_documents()

    def document_exists(self, document_id: str) -> bool:
        """Check if document exists"""
        return self.documents.document_exists(document_id)

    def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """Get document metadata"""
        return self.documents.get_document_metadata(document_id)

    # === Chunk Operations (backward compatibility) ===

    def upload_chunk(self, document_id: str, chunk_id: str,
                    chunk_text: str, metadata: Optional[Dict[str, Any]] = None,
                    scope: Any = None) -> bool:
        """Upload single chunk"""
        return self.chunks.upload_chunk(document_id, chunk_id, chunk_text, metadata, scope)

    def upload_chunks(self, chunks: List[Dict[str, Any]], document_id: str,
                     scope: Any = None) -> bool:
        """Upload multiple chunks"""
        return self.chunks.upload_chunks(chunks, document_id, scope)

    def save_chunks_batch(self, document_id: str, chunks_data: List[Dict[str, Any]]) -> List[str]:
        """Save multiple chunks (compatibility)"""
        return self.chunks.save_chunks_batch(document_id, chunks_data)

    def get_chunks(self, document_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get all chunks for a document"""
        return self.chunks.get_chunks(document_id)

    # === Cache Operations (backward compatibility) ===

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get from cache (private method for compatibility)"""
        return self.cache.get(key)

    def _add_to_cache(self, key: str, data: Any):
        """Add to cache (private method for compatibility)"""
        self.cache.set(key, data)

    def _invalidate_cache(self, document_id: str):
        """Invalidate cache for document (private method for compatibility)"""
        self.cache.invalidate(document_id)

    def clear_cache(self):
        """Clear all cache"""
        self.cache.clear()

    # === MinIO Bucket Operations ===

    def _ensure_buckets(self):
        """Ensure buckets exist (called by old code)"""
        # This is handled in client initialization
        pass


# Create singleton instance for backward compatibility
# This allows: from app.storage import storage
storage = Storage()

# Also export MinIOStorage for complete backward compatibility
MinIOStorage = Storage

# Export main classes for direct use if needed
__all__ = [
    'storage',
    'Storage',
    'MinIOStorage',
    'DocumentStorage',
    'ChunkStorage',
    'StorageCache',
    'MinIOClientManager'
]