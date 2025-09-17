"""
Indexing package for vector database operations

This package provides vector indexing implementations:
- Milvus vector database support
- Extensible for other vector databases
"""
import logging
from typing import Optional

from app.core.indexing.base import AbstractIndexer
from app.core.indexing.milvus_indexer import MilvusIndexer
from app.core.indexing.utils import (
    generate_chunk_id,
    generate_document_id,
    normalize_embedding,
    batch_embeddings,
    calculate_similarity,
    filter_search_results,
    merge_search_results,
    prepare_chunk_metadata,
    validate_embeddings
)

logger = logging.getLogger(__name__)


def create_indexer(
    backend: str = "milvus",
    **kwargs
) -> AbstractIndexer:
    """
    Factory function to create vector indexer based on backend

    Args:
        backend: Vector database backend ('milvus', etc.)
        **kwargs: Additional arguments for the specific implementation

    Returns:
        Vector indexer instance
    """
    if backend.lower() == "milvus":
        logger.info("Creating Milvus indexer")
        return MilvusIndexer(**kwargs)
    else:
        # Default to Milvus for now
        logger.warning(f"Unknown backend '{backend}', using Milvus")
        return MilvusIndexer(**kwargs)


# Create default indexer instance
try:
    default_indexer = create_indexer(backend="milvus")
    logger.info("Default indexer initialized with Milvus backend")
except Exception as e:
    logger.error(f"Failed to initialize default indexer: {e}")
    default_indexer = None


# Export all classes and functions
__all__ = [
    # Base classes
    'AbstractIndexer',
    # Implementations
    'MilvusIndexer',
    # Factory
    'create_indexer',
    'default_indexer',
    # Utils
    'generate_chunk_id',
    'generate_document_id',
    'normalize_embedding',
    'batch_embeddings',
    'calculate_similarity',
    'filter_search_results',
    'merge_search_results',
    'prepare_chunk_metadata',
    'validate_embeddings'
]