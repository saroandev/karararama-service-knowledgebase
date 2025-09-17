"""
Backward compatibility module for retrieval operations.

This file is kept for backward compatibility.
All imports from 'app.retrieve' will be redirected to the new package structure.
New code should use 'from app.core.retrieval import ...' directly.
"""
import logging
import warnings
from typing import List, Dict, Any, Optional

# Import from new location
from app.core.retrieval import (
    AbstractRetriever,
    VectorSearchRetriever,
    RerankerRetriever,
    HybridRetriever,
    Retriever as ModernRetriever,
    create_retriever,
    default_retriever,
    # Utils
    build_filter_expression,
    calculate_text_similarity,
    apply_mmr_selection
)

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "Importing from app.retrieve is deprecated. Use app.core.retrieval instead.",
    DeprecationWarning,
    stacklevel=2
)


# Legacy Retriever class for backward compatibility
class Retriever(HybridRetriever):
    """
    Legacy Retriever class for backward compatibility.
    This wraps the new HybridRetriever implementation.
    """

    def __init__(self, use_reranker: bool = True):
        """Initialize retriever"""
        warnings.warn(
            "Retriever is deprecated. Use HybridRetriever from app.core.retrieval",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(use_reranker)
        logger.info("Legacy Retriever initialized with HybridRetriever backend")

    # All methods are inherited from HybridRetriever
    # The following are explicitly defined for clarity and IDE support

    def _build_filter_expression(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        """Build filter expression (legacy method name)"""
        return build_filter_expression(filters)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity (legacy method name)"""
        return calculate_text_similarity(text1, text2)


# Create singleton instance for backward compatibility
try:
    retriever = Retriever()
    logger.info("Legacy retriever singleton instance created")
except Exception as e:
    logger.error(f"Failed to create legacy retriever: {e}")
    # Fallback to default retriever from new package
    retriever = default_retriever