"""
Reranker retriever implementation
"""
import logging
from typing import List, Dict, Any, Optional

from app.core.retrieval.vector_search import VectorSearchRetriever
from app.config import settings

logger = logging.getLogger(__name__)

# Lazy import for CrossEncoder to avoid TensorFlow loading
CrossEncoder = None
CROSSENCODER_AVAILABLE = False


class RerankerRetriever(VectorSearchRetriever):
    """
    Retriever with reranking capabilities using cross-encoder models
    """

    def __init__(self, use_reranker: bool = True):
        """
        Initialize the reranker retriever

        Args:
            use_reranker: Whether to use reranking by default
        """
        super().__init__(use_reranker)
        self.reranker = None
        if use_reranker:
            self.reranker = self._load_reranker()

    def _load_reranker(self) -> Optional['CrossEncoder']:
        """
        Load the reranking model

        Returns:
            CrossEncoder model or None if loading fails
        """
        global CrossEncoder, CROSSENCODER_AVAILABLE

        if not CROSSENCODER_AVAILABLE:
            try:
                from sentence_transformers import CrossEncoder
                CROSSENCODER_AVAILABLE = True
            except ImportError:
                logger.warning("CrossEncoder not available - skipping reranker loading")
                return None

        try:
            model = CrossEncoder(
                settings.RERANKER_MODEL,
                max_length=512
            )
            logger.info(f"Loaded reranker: {settings.RERANKER_MODEL}")
            return model
        except Exception as e:
            logger.error(f"Error loading reranker: {e}")
            return None

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_reranker: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks with optional reranking

        Args:
            query: Query text
            top_k: Number of results to return
            filters: Optional filters for search
            use_reranker: Whether to use reranker (overrides default)

        Returns:
            List of relevant chunks with scores
        """
        # Determine if we should use reranker
        should_rerank = use_reranker if use_reranker is not None else self.use_reranker

        # If reranking, retrieve more candidates
        if should_rerank and self.reranker:
            initial_k = min(top_k * 3, 100)
        else:
            initial_k = top_k

        # Get initial results from vector search
        results = super().retrieve(query, initial_k, filters)

        # Apply reranking if needed
        if should_rerank and self.reranker and results:
            results = self._rerank_results(query, results, top_k)
        else:
            results = results[:top_k]

        return results

    def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results using cross-encoder

        Args:
            query: Query text
            results: Initial search results
            top_k: Number of results to return

        Returns:
            Reranked results
        """
        if not results or not self.reranker:
            return results[:top_k]

        # Prepare pairs for reranking
        pairs = [[query, result["text"]] for result in results]

        # Get reranking scores
        try:
            scores = self.reranker.predict(pairs)

            # Add reranking scores to results
            for i, result in enumerate(results):
                result["rerank_score"] = float(scores[i])
                result["original_score"] = result.get("score", 0)

            # Sort by reranking score
            results.sort(key=lambda x: x["rerank_score"], reverse=True)

            logger.debug(f"Reranked {len(results)} results")

        except Exception as e:
            logger.error(f"Error during reranking: {e}")

        return results[:top_k]

    def set_reranker_model(self, model_name: str):
        """
        Change the reranker model

        Args:
            model_name: Name of the new reranker model
        """
        try:
            self.reranker = CrossEncoder(model_name, max_length=512)
            logger.info(f"Changed reranker to: {model_name}")
        except Exception as e:
            logger.error(f"Error changing reranker model: {e}")

    def enable_reranking(self):
        """Enable reranking for future retrievals"""
        self.use_reranker = True
        if not self.reranker:
            self.reranker = self._load_reranker()

    def disable_reranking(self):
        """Disable reranking for future retrievals"""
        self.use_reranker = False