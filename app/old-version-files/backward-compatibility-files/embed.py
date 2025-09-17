"""
Backward compatibility module for embeddings.

This file is kept for backward compatibility.
All imports from 'app.embed' will be redirected to the new package structure.
New code should use 'from app.core.embeddings import ...' directly.
"""
import logging
import warnings
from typing import List, Optional, Union
import numpy as np

# Import from new location
from app.core.embeddings import (
    AbstractEmbedding,
    OpenAIEmbedding,
    LocalEmbedding,
    MultilingualEmbedding,
    CachedLocalEmbedding,
    create_embedding_generator,
    default_embedding_generator,
    SENTENCE_TRANSFORMERS_AVAILABLE
)
from app.config import settings

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "Importing from app.embed is deprecated. Use app.core.embeddings instead.",
    DeprecationWarning,
    stacklevel=2
)


# Legacy class names for compatibility
class EmbeddingGenerator:
    """
    Legacy EmbeddingGenerator class for backward compatibility.
    This wraps the new LocalEmbedding class.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = 32
    ):
        """Initialize embedding generator"""
        warnings.warn(
            "EmbeddingGenerator is deprecated. Use LocalEmbedding or OpenAIEmbedding from app.core.embeddings",
            DeprecationWarning,
            stacklevel=2
        )

        # Use OpenAI by default as per user preference
        provider = settings.EMBEDDING_PROVIDER or 'openai'

        if provider == 'openai':
            self._impl = OpenAIEmbedding(
                model_name=model_name,
                batch_size=batch_size or 32
            )
        else:
            # Fallback to local if specified
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.warning("SentenceTransformers not available, using OpenAI instead")
                self._impl = OpenAIEmbedding(
                    model_name=model_name,
                    batch_size=batch_size or 32
                )
            else:
                self._impl = LocalEmbedding(
                    model_name=model_name,
                    device=device,
                    batch_size=batch_size or 32
                )

        # Expose attributes for compatibility
        self.model_name = self._impl.model_name
        self.dimension = self._impl.dimension
        self.batch_size = batch_size or 32

    def generate_embedding(self, text: Union[str, List[str]]) -> np.ndarray:
        """Generate embeddings for text"""
        return self._impl.generate_embedding(text)

    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts"""
        return self._impl.generate_embeddings_batch(texts, show_progress=show_progress)

    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self._impl.get_dimension()

    def warmup(self):
        """Warmup the model with a dummy input"""
        self._impl.warmup()


# Legacy MultilingualEmbedding for compatibility
class MultilingualEmbedding(EmbeddingGenerator):
    """Legacy MultilingualEmbedding class for backward compatibility"""

    def __init__(self):
        warnings.warn(
            "MultilingualEmbedding from app.embed is deprecated. Use from app.core.embeddings",
            DeprecationWarning,
            stacklevel=2
        )
        # Initialize with a multilingual model
        super().__init__(model_name="intfloat/multilingual-e5-base")

    def generate_embedding_with_instruction(
        self,
        text: str,
        instruction: Optional[str] = None
    ) -> np.ndarray:
        """Generate embedding with optional instruction prefix"""
        if instruction:
            text = f"{instruction}: {text}"
        return self.generate_embedding(text)


# Legacy CachedEmbeddingGenerator for compatibility
class CachedEmbeddingGenerator(EmbeddingGenerator):
    """Legacy CachedEmbeddingGenerator class for backward compatibility"""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "CachedEmbeddingGenerator from app.embed is deprecated. Use CachedLocalEmbedding from app.core.embeddings",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)
        self.cache = {}

    def generate_embedding(self, text: Union[str, List[str]]) -> np.ndarray:
        """Generate embeddings with caching"""
        if isinstance(text, str):
            cache_key = hash(text)
            if cache_key in self.cache:
                logger.debug(f"Cache hit for text hash: {cache_key}")
                return self.cache[cache_key]

            embedding = super().generate_embedding(text)
            self.cache[cache_key] = embedding
            return embedding
        else:
            # For batch, generate without cache (simplified)
            return super().generate_embedding(text)

    def clear_cache(self):
        """Clear the embedding cache"""
        self.cache.clear()
        logger.info("Embedding cache cleared")


# Create singleton instance for backward compatibility
# Using the default from the new module
embedding_generator = default_embedding_generator


# For backward compatibility with OpenAIEmbedding imports
# (Used in tests)
class OpenAIEmbedding(OpenAIEmbedding):
    """Re-export OpenAIEmbedding for backward compatibility"""
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs):
        # Handle 'model' parameter name (tests use 'model' instead of 'model_name')
        if model and 'model_name' not in kwargs:
            kwargs['model_name'] = model
        super().__init__(api_key=api_key, **kwargs)


# Re-export HuggingFaceEmbedding as LocalEmbedding for tests
HuggingFaceEmbedding = LocalEmbedding


# Export everything for backward compatibility
__all__ = [
    'EmbeddingGenerator',
    'MultilingualEmbedding',
    'CachedEmbeddingGenerator',
    'embedding_generator',
    'OpenAIEmbedding',
    'HuggingFaceEmbedding',
    # Also export new names
    'AbstractEmbedding',
    'LocalEmbedding',
    'CachedLocalEmbedding',
    'create_embedding_generator',
    'default_embedding_generator'
]