"""
Embeddings package for text embedding generation

This package provides multiple embedding implementations:
- OpenAI embeddings (default)
- Local embeddings using SentenceTransformers
"""
import logging
from typing import Optional

from app.core.embeddings.base import AbstractEmbedding
from app.core.embeddings.openai_embeddings import OpenAIEmbedding
from app.core.embeddings.local_embeddings import (
    LocalEmbedding,
    MultilingualEmbedding,
    CachedLocalEmbedding,
    SENTENCE_TRANSFORMERS_AVAILABLE
)
from app.config import settings

logger = logging.getLogger(__name__)


def create_embedding_generator(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    **kwargs
) -> AbstractEmbedding:
    """
    Factory function to create embedding generator based on provider

    Args:
        provider: Embedding provider ('openai' or 'local')
        model_name: Model name to use
        **kwargs: Additional arguments for the specific implementation

    Returns:
        Embedding generator instance
    """
    provider = provider or settings.EMBEDDING_PROVIDER or 'openai'

    if provider.lower() == 'openai':
        logger.info("Creating OpenAI embedding generator")
        return OpenAIEmbedding(
            model_name=model_name,
            **kwargs
        )
    elif provider.lower() in ['local', 'sentence-transformers', 'huggingface']:
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning(
                "SentenceTransformers not available, falling back to OpenAI. "
                "Install with: pip install sentence-transformers"
            )
            return OpenAIEmbedding(
                model_name=model_name,
                **kwargs
            )
        logger.info("Creating local embedding generator")
        return LocalEmbedding(
            model_name=model_name,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


# Create default embedding generator instance
# Using OpenAI by default as per user preference
try:
    default_embedding_generator = create_embedding_generator(provider='openai')
    logger.info("Default embedding generator initialized with OpenAI")
except Exception as e:
    logger.warning(f"Failed to initialize default embedding generator: {e}")
    default_embedding_generator = None


# Export all classes and functions
__all__ = [
    'AbstractEmbedding',
    'OpenAIEmbedding',
    'LocalEmbedding',
    'MultilingualEmbedding',
    'CachedLocalEmbedding',
    'create_embedding_generator',
    'default_embedding_generator',
    'SENTENCE_TRANSFORMERS_AVAILABLE'
]