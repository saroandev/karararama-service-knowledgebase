import logging
from typing import List, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = 32
    ):
        """
        Initialize embedding generator
        
        Args:
            model_name: Name of the embedding model
            device: Device to run model on ("cuda", "cpu", or None for auto)
            batch_size: Batch size for encoding
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        
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
        logger.info(f"Loaded embedding model: {self.model_name}, dimension: {self.dimension}")
    
    def _load_model(self) -> SentenceTransformer:
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
        Generate embeddings for text
        
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
                show_progress_bar=len(text) > 100,
                convert_to_numpy=True,
                normalize_embeddings=True  # Important for cosine similarity
            )
            
            if single_input:
                return embeddings[0]
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[np.ndarray]:
        """
        Generate embeddings for a batch of texts
        
        Args:
            texts: List of texts
            show_progress: Whether to show progress bar
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        return [emb for emb in embeddings]
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension
    
    def warmup(self):
        """Warmup the model with a dummy input"""
        try:
            _ = self.generate_embedding("warmup text")
            logger.info("Model warmup complete")
        except Exception as e:
            logger.error(f"Error during warmup: {e}")


class MultilingualEmbedding(EmbeddingGenerator):
    """Specialized class for multilingual embeddings"""
    
    def __init__(self):
        # BGE-M3 supports multiple languages
        super().__init__(model_name="BAAI/bge-m3")
    
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
            # BGE models can use instruction prefixes for better retrieval
            text = f"{instruction}: {text}"
        
        return self.generate_embedding(text)


class CachedEmbeddingGenerator(EmbeddingGenerator):
    """Embedding generator with caching support"""
    
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


# Singleton instance
embedding_generator = EmbeddingGenerator()