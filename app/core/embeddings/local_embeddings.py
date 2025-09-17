"""
Local embedding implementation using SentenceTransformers
"""
import logging
from typing import List, Union, Optional
import numpy as np

from app.core.embeddings.base import AbstractEmbedding
from app.config import settings

logger = logging.getLogger(__name__)

# Optional import - SentenceTransformers may not be installed
try:
    from sentence_transformers import SentenceTransformer
    import torch
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("SentenceTransformers not available. Install with: pip install sentence-transformers")


class LocalEmbedding(AbstractEmbedding):
    """Local embedding implementation using SentenceTransformers"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: int = 32
    ):
        """
        Initialize local embedding generator

        Args:
            model_name: Name of the SentenceTransformer model
            device: Device to run model on ("cuda", "cpu", or None for auto)
            batch_size: Batch size for encoding
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "SentenceTransformers is not installed. "
                "Install with: pip install sentence-transformers"
            )

        model_name = model_name or settings.EMBEDDING_MODEL or "intfloat/multilingual-e5-small"
        super().__init__(model_name)

        self.batch_size = batch_size

        # Determine device
        if device:
            self.device = device
        elif torch.cuda.is_available():
            self.device = "cuda"
            logger.info("Using CUDA for embeddings")
        else:
            self.device = "cpu"
            logger.info("Using CPU for embeddings")

        # Load model
        self.model = self._load_model()
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Loaded local embedding model: {self.model_name}, dimension: {self.dimension}")

    def _load_model(self) -> 'SentenceTransformer':
        """Load the sentence transformer model"""
        try:
            model = SentenceTransformer(
                self.model_name,
                device=self.device
            )
            return model
        except Exception as e:
            logger.error(f"Error loading model {self.model_name}: {e}")
            raise

    def generate_embedding(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings for text(s)

        Args:
            text: Single text or list of texts

        Returns:
            Embedding vector(s) as numpy array
        """
        if isinstance(text, str):
            text = [text]
            single_input = True
        else:
            single_input = False

        try:
            # Generate embeddings
            embeddings = self.model.encode(
                text,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True  # Important for cosine similarity
            )

            if single_input:
                return embeddings[0]
            return embeddings

        except Exception as e:
            logger.error(f"Error generating local embeddings: {e}")
            raise

    def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False
    ) -> List[np.ndarray]:
        """
        Generate embeddings for a batch of texts

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        batch_size = batch_size or self.batch_size

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        return [emb for emb in embeddings]

    def get_dimension(self) -> int:
        """
        Get the dimension of embeddings

        Returns:
            Embedding dimension
        """
        return self.dimension


class MultilingualEmbedding(LocalEmbedding):
    """Specialized class for multilingual embeddings"""

    def __init__(self, device: Optional[str] = None, batch_size: int = 32):
        """
        Initialize multilingual embedding generator

        Args:
            device: Device to run model on
            batch_size: Batch size for encoding
        """
        # Use a multilingual model by default
        super().__init__(
            model_name="intfloat/multilingual-e5-base",
            device=device,
            batch_size=batch_size
        )

    def generate_embedding_with_instruction(
        self,
        text: str,
        instruction: Optional[str] = None
    ) -> np.ndarray:
        """
        Generate embedding with optional instruction prefix

        Args:
            text: Text to embed
            instruction: Optional instruction to prepend

        Returns:
            Embedding vector
        """
        if instruction:
            # E5 models benefit from instruction prefixes
            text = f"{instruction}: {text}"

        return self.generate_embedding(text)


class CachedLocalEmbedding(LocalEmbedding):
    """Local embedding generator with caching support"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = {}

    def generate_embedding(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings with caching

        Args:
            text: Text(s) to embed

        Returns:
            Embedding vector(s)
        """
        if isinstance(text, str):
            # Check cache for single text
            cache_key = hash(text)
            if cache_key in self.cache:
                logger.debug(f"Cache hit for text hash: {cache_key}")
                return self.cache[cache_key]

            # Generate and cache
            embedding = super().generate_embedding(text)
            self.cache[cache_key] = embedding
            return embedding
        else:
            # For batch, check individual items
            results = []
            uncached_texts = []
            uncached_indices = []

            for i, t in enumerate(text):
                cache_key = hash(t)
                if cache_key in self.cache:
                    results.append((i, self.cache[cache_key]))
                else:
                    uncached_texts.append(t)
                    uncached_indices.append(i)

            # Generate embeddings for uncached texts
            if uncached_texts:
                new_embeddings = super().generate_embedding(uncached_texts)
                for i, idx in enumerate(uncached_indices):
                    embedding = new_embeddings[i]
                    cache_key = hash(uncached_texts[i])
                    self.cache[cache_key] = embedding
                    results.append((idx, embedding))

            # Sort by original index and return
            results.sort(key=lambda x: x[0])
            return np.array([emb for _, emb in results])

    def clear_cache(self):
        """Clear the embedding cache"""
        self.cache.clear()
        logger.info("Embedding cache cleared")