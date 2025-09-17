"""
Retrieval package for document search and retrieval operations

This package provides various retrieval implementations:
- Vector similarity search
- Reranking with cross-encoders
- Diverse retrieval with MMR
- Hybrid search combining semantic and keyword search
"""
import logging
from typing import Optional

from app.core.retrieval.base import AbstractRetriever
from app.core.retrieval.vector_search import VectorSearchRetriever
from app.core.retrieval.reranker import RerankerRetriever
from app.core.retrieval.hybrid_retriever import HybridRetriever
from app.core.retrieval.utils import (
    build_filter_expression,
    calculate_text_similarity,
    enrich_results_from_storage,
    apply_mmr_selection,
    deduplicate_results,
    merge_search_results,
    reciprocal_rank_fusion,
    filter_by_score_threshold,
    group_results_by_document
)

logger = logging.getLogger(__name__)


def create_retriever(
    retriever_type: str = "hybrid",
    use_reranker: Optional[bool] = None,
    **kwargs
) -> AbstractRetriever:
    """
    Factory function to create retriever based on type

    Args:
        retriever_type: Type of retriever ('vector', 'reranker', 'hybrid')
        use_reranker: Whether to use reranking (None uses default from settings)
        **kwargs: Additional arguments for specific implementations

    Returns:
        Retriever instance
    """
    # Determine reranker setting
    if use_reranker is None:
        from app.config import settings
        use_reranker = getattr(settings, 'USE_RERANKER', True)

    if retriever_type.lower() == "vector":
        logger.info("Creating VectorSearchRetriever")
        return VectorSearchRetriever(use_reranker=False)
    elif retriever_type.lower() == "reranker":
        logger.info("Creating RerankerRetriever with reranking enabled")
        return RerankerRetriever(use_reranker=True)
    elif retriever_type.lower() == "hybrid":
        logger.info(f"Creating HybridRetriever (reranking={use_reranker})")
        return HybridRetriever(use_reranker=use_reranker)
    else:
        # Default to hybrid
        logger.warning(f"Unknown retriever type '{retriever_type}', using hybrid")
        return HybridRetriever(use_reranker=use_reranker)


# Create default retriever instance (backward compatibility)
try:
    from app.config import settings
    default_retriever_type = getattr(settings, 'RETRIEVER_TYPE', 'hybrid')
    default_use_reranker = getattr(settings, 'USE_RERANKER', True)

    default_retriever = create_retriever(
        retriever_type=default_retriever_type,
        use_reranker=default_use_reranker
    )
    logger.info(f"Default retriever initialized: {default_retriever_type} (reranking={default_use_reranker})")
except Exception as e:
    logger.error(f"Failed to initialize default retriever: {e}")
    default_retriever = None


# Legacy Retriever class for backward compatibility
class Retriever(HybridRetriever):
    """
    Legacy Retriever class for backward compatibility.
    This is an alias for HybridRetriever.
    """
    def __init__(self, use_reranker: bool = True):
        logger.warning(
            "Using legacy Retriever class. Consider using HybridRetriever from app.core.retrieval"
        )
        super().__init__(use_reranker)


# Export all classes and functions
__all__ = [
    # Base classes
    'AbstractRetriever',
    # Implementations
    'VectorSearchRetriever',
    'RerankerRetriever',
    'HybridRetriever',
    'Retriever',  # Legacy compatibility
    # Factory
    'create_retriever',
    'default_retriever',
    # Utils
    'build_filter_expression',
    'calculate_text_similarity',
    'enrich_results_from_storage',
    'apply_mmr_selection',
    'deduplicate_results',
    'merge_search_results',
    'reciprocal_rank_fusion',
    'filter_by_score_threshold',
    'group_results_by_document'
]