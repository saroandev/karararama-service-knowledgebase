"""
Backward compatibility module for vector indexing.

This file is kept for backward compatibility.
All imports from 'app.index' will be redirected to the new package structure.
New code should use 'from app.core.indexing import ...' directly.
"""
import logging
import warnings
from typing import List, Dict, Any, Optional
import numpy as np

# Import from new location
from app.core.indexing import (
    AbstractIndexer,
    MilvusIndexer as NewMilvusIndexer,
    create_indexer,
    default_indexer
)

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "Importing from app.index is deprecated. Use app.core.indexing instead.",
    DeprecationWarning,
    stacklevel=2
)


# Legacy MilvusIndexer class for backward compatibility
class MilvusIndexer:
    """
    Legacy MilvusIndexer class for backward compatibility.
    This wraps the new MilvusIndexer implementation.
    """

    def __init__(self):
        """Initialize Milvus indexer"""
        warnings.warn(
            "MilvusIndexer from app.index is deprecated. Use MilvusIndexer from app.core.indexing",
            DeprecationWarning,
            stacklevel=2
        )

        self._impl = NewMilvusIndexer()

        # Expose attributes for compatibility
        self.host = self._impl.host
        self.port = self._impl.port
        self.collection_name = self._impl.collection_name
        self.collection = self._impl.collection

    def _connect(self):
        """Connect to Milvus server"""
        return self._impl.connect()

    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        # This is handled in the new implementation's __init__
        pass

    def _create_collection(self):
        """Create Milvus collection with schema"""
        return self._impl.create_collection()

    def insert_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[np.ndarray]) -> int:
        """
        Insert chunks with embeddings into Milvus

        Args:
            chunks: List of chunk dictionaries
            embeddings: List of embedding vectors

        Returns:
            Number of inserted items
        """
        return self._impl.insert_chunks(chunks, embeddings)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional filter expression (string format for backward compatibility)

        Returns:
            List of search results with scores
        """
        # Convert string filter to dict if needed
        filter_dict = None
        if filters:
            # Simple parsing for backward compatibility
            # Assumes filters like 'document_id == "doc123"'
            try:
                if '==' in filters:
                    parts = filters.split('==')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().strip('"')
                        filter_dict = {key: value}
            except:
                pass

        return self._impl.search(query_embedding, top_k, filter_dict)

    def delete_by_document(self, document_id: str) -> bool:
        """
        Delete all chunks for a document

        Args:
            document_id: Document identifier

        Returns:
            Success status
        """
        return self._impl.delete_by_document(document_id)

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        return self._impl.get_collection_stats()

    def create_partition(self, partition_name: str):
        """Create a partition in the collection"""
        return self._impl.create_partition(partition_name)

    def drop_collection(self):
        """Drop the entire collection"""
        return self._impl.drop_collection()

    def rebuild_index(self):
        """Rebuild the vector index"""
        return self._impl.rebuild_index()

    def batch_search(
        self,
        query_embeddings: List[np.ndarray],
        top_k: int = 10,
        filters: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Batch search for multiple queries

        Args:
            query_embeddings: List of query embedding vectors
            top_k: Number of results per query
            filters: Optional filter expression

        Returns:
            List of search results for each query
        """
        # Convert string filter to dict if needed
        filter_dict = None
        if filters:
            try:
                if '==' in filters:
                    parts = filters.split('==')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().strip('"')
                        filter_dict = {key: value}
            except:
                pass

        return self._impl.batch_search(query_embeddings, top_k, filter_dict)


# Create singleton instance for backward compatibility
milvus_indexer = MilvusIndexer() if default_indexer else None


# Export everything for backward compatibility
__all__ = [
    'MilvusIndexer',
    'milvus_indexer',
    # Also export new names
    'AbstractIndexer',
    'create_indexer',
    'default_indexer'
]