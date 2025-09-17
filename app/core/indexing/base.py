"""
Base classes for vector indexing
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np


class AbstractIndexer(ABC):
    """Abstract base class for all vector indexer implementations"""

    def __init__(self, collection_name: Optional[str] = None):
        """
        Initialize the indexer

        Args:
            collection_name: Name of the collection/index
        """
        self.collection_name = collection_name

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the vector database

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def create_collection(self, dimension: int, **kwargs) -> bool:
        """
        Create a new collection/index

        Args:
            dimension: Dimension of vectors
            **kwargs: Additional configuration parameters

        Returns:
            True if creation successful, False otherwise
        """
        pass

    @abstractmethod
    def insert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[np.ndarray]
    ) -> int:
        """
        Insert chunks with embeddings into the index

        Args:
            chunks: List of chunk dictionaries with metadata
            embeddings: List of embedding vectors

        Returns:
            Number of successfully inserted items
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters to apply

        Returns:
            List of search results with scores and metadata
        """
        pass

    @abstractmethod
    def delete_by_document(self, document_id: str) -> bool:
        """
        Delete all chunks for a specific document

        Args:
            document_id: Document identifier

        Returns:
            True if deletion successful, False otherwise
        """
        pass

    @abstractmethod
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection

        Returns:
            Dictionary with collection statistics
        """
        pass

    def batch_insert(
        self,
        chunks_list: List[List[Dict[str, Any]]],
        embeddings_list: List[List[np.ndarray]]
    ) -> int:
        """
        Insert multiple batches of chunks

        Args:
            chunks_list: List of chunk batches
            embeddings_list: List of embedding batches

        Returns:
            Total number of inserted items
        """
        total_inserted = 0
        for chunks, embeddings in zip(chunks_list, embeddings_list):
            total_inserted += self.insert_chunks(chunks, embeddings)
        return total_inserted

    def batch_search(
        self,
        query_embeddings: List[np.ndarray],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Search for multiple queries

        Args:
            query_embeddings: List of query embedding vectors
            top_k: Number of results per query
            filters: Optional filters to apply

        Returns:
            List of search results for each query
        """
        results = []
        for query_embedding in query_embeddings:
            results.append(self.search(query_embedding, top_k, filters))
        return results

    def is_healthy(self) -> bool:
        """
        Check if the indexer is healthy and operational

        Returns:
            True if healthy, False otherwise
        """
        try:
            stats = self.get_collection_stats()
            return bool(stats)
        except:
            return False