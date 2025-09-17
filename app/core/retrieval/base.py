"""
Base classes for retrieval operations
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np


class AbstractRetriever(ABC):
    """Abstract base class for all retriever implementations"""

    def __init__(self, use_reranker: bool = False):
        """
        Initialize the retriever

        Args:
            use_reranker: Whether to use reranking by default
        """
        self.use_reranker = use_reranker

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_reranker: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query

        Args:
            query: Query text
            top_k: Number of results to return
            filters: Optional filters for search
            use_reranker: Whether to use reranker (overrides default)

        Returns:
            List of relevant chunks with scores and metadata
        """
        pass

    @abstractmethod
    def retrieve_diverse(
        self,
        query: str,
        top_k: int = 10,
        diversity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve diverse results using MMR (Maximal Marginal Relevance)

        Args:
            query: Query text
            top_k: Number of results to return
            diversity_threshold: Similarity threshold for diversity (0-1)

        Returns:
            List of diverse search results
        """
        pass

    @abstractmethod
    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword search

        Args:
            query: Query text
            top_k: Number of results to return
            keyword_weight: Weight for keyword search (0-1)

        Returns:
            List of combined search results
        """
        pass

    def batch_retrieve(
        self,
        queries: List[str],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Retrieve results for multiple queries

        Args:
            queries: List of query texts
            top_k: Number of results per query
            filters: Optional filters for search

        Returns:
            List of search results for each query
        """
        results = []
        for query in queries:
            results.append(self.retrieve(query, top_k, filters))
        return results

    def is_healthy(self) -> bool:
        """
        Check if the retriever is healthy and operational

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try a simple search
            results = self.retrieve("test", top_k=1)
            return True
        except:
            return False