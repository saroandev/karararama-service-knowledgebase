"""
Hybrid retriever combining all retrieval strategies
"""
import logging
from typing import List, Dict, Any, Optional

from app.core.retrieval.reranker import RerankerRetriever
from app.config import settings

logger = logging.getLogger(__name__)


class HybridRetriever(RerankerRetriever):
    """
    Advanced retriever combining vector search, reranking, diversity, and hybrid search
    This is the main retriever that combines all strategies
    """

    def __init__(self, use_reranker: bool = True):
        """
        Initialize the hybrid retriever

        Args:
            use_reranker: Whether to use reranking by default
        """
        super().__init__(use_reranker)
        logger.info("Initialized HybridRetriever with all retrieval capabilities")

    def retrieve_with_strategy(
        self,
        query: str,
        strategy: str = "default",
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using a specific strategy

        Args:
            query: Query text
            strategy: Retrieval strategy ('default', 'diverse', 'hybrid')
            top_k: Number of results to return
            filters: Optional filters for search
            **kwargs: Additional strategy-specific parameters

        Returns:
            List of search results
        """
        if strategy == "diverse":
            diversity_threshold = kwargs.get("diversity_threshold", 0.7)
            return self.retrieve_diverse(query, top_k, diversity_threshold)
        elif strategy == "hybrid":
            keyword_weight = kwargs.get("keyword_weight", 0.3)
            return self.hybrid_search(query, top_k, keyword_weight)
        else:  # default
            use_reranker = kwargs.get("use_reranker", self.use_reranker)
            return self.retrieve(query, top_k, filters, use_reranker)

    def retrieve_multi_strategy(
        self,
        query: str,
        strategies: List[str],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        fusion_method: str = "rrf"
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using multiple strategies and fuse results

        Args:
            query: Query text
            strategies: List of strategies to use
            top_k: Number of results to return
            filters: Optional filters for search
            fusion_method: Method to fuse results ('rrf' for Reciprocal Rank Fusion)

        Returns:
            Fused search results
        """
        all_results = []

        for strategy in strategies:
            results = self.retrieve_with_strategy(
                query,
                strategy,
                top_k * 2,  # Get more candidates for fusion
                filters
            )
            all_results.append(results)

        # Fuse results
        if fusion_method == "rrf":
            return self._reciprocal_rank_fusion(all_results, top_k)
        else:
            # Simple merge and deduplicate
            merged = []
            seen_ids = set()
            for results in all_results:
                for result in results:
                    chunk_id = result.get("chunk_id", result.get("id"))
                    if chunk_id and chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        merged.append(result)
            return merged[:top_k]

    def _reciprocal_rank_fusion(
        self,
        result_lists: List[List[Dict[str, Any]]],
        top_k: int,
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Fuse multiple result lists using Reciprocal Rank Fusion

        Args:
            result_lists: List of result lists from different strategies
            top_k: Number of results to return
            k: RRF parameter (typically 60)

        Returns:
            Fused results
        """
        # Calculate RRF scores
        rrf_scores = {}

        for results in result_lists:
            for rank, result in enumerate(results):
                chunk_id = result.get("chunk_id", result.get("id"))
                if chunk_id:
                    if chunk_id not in rrf_scores:
                        rrf_scores[chunk_id] = {
                            "score": 0,
                            "result": result
                        }
                    # Add reciprocal rank score
                    rrf_scores[chunk_id]["score"] += 1 / (k + rank + 1)

        # Sort by RRF score
        sorted_results = sorted(
            rrf_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )

        # Extract results and add RRF scores
        final_results = []
        for item in sorted_results[:top_k]:
            result = item["result"]
            result["rrf_score"] = item["score"]
            final_results.append(result)

        return final_results

    def adaptive_retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Adaptively choose retrieval strategy based on query characteristics

        Args:
            query: Query text
            top_k: Number of results to return
            filters: Optional filters

        Returns:
            Search results using the most appropriate strategy
        """
        # Simple heuristics for strategy selection
        query_length = len(query.split())
        has_keywords = any(word in query.lower() for word in ["exact", "specific", "precisely"])
        is_broad = any(word in query.lower() for word in ["overview", "general", "summary", "explain"])

        if has_keywords:
            # Use hybrid search for keyword-heavy queries
            logger.debug("Using hybrid strategy for keyword-heavy query")
            return self.hybrid_search(query, top_k, keyword_weight=0.5)
        elif is_broad:
            # Use diverse retrieval for broad queries
            logger.debug("Using diverse strategy for broad query")
            return self.retrieve_diverse(query, top_k, diversity_threshold=0.8)
        elif query_length > 10:
            # Use reranking for complex queries
            logger.debug("Using reranked retrieval for complex query")
            return self.retrieve(query, top_k, filters, use_reranker=True)
        else:
            # Default retrieval
            logger.debug("Using default retrieval strategy")
            return self.retrieve(query, top_k, filters)

    def get_retrieval_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the retriever configuration

        Returns:
            Dictionary with retriever statistics
        """
        stats = {
            "reranker_enabled": self.use_reranker,
            "reranker_loaded": self.reranker is not None,
            "indexer_healthy": self.indexer.is_healthy() if self.indexer else False,
            "embedder_dimension": self.embedder.get_dimension() if self.embedder else 0,
            "supported_strategies": ["default", "diverse", "hybrid", "adaptive"],
            "reranker_model": settings.RERANKER_MODEL if self.reranker else None
        }
        return stats