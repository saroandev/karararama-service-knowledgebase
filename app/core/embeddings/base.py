"""
Base classes for embedding generation
"""
from abc import ABC, abstractmethod
from typing import List, Union, Optional
import numpy as np


class AbstractEmbedding(ABC):
    """Abstract base class for all embedding implementations"""

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the embedding generator

        Args:
            model_name: Name of the embedding model
        """
        self.model_name = model_name
        self.dimension = None

    @abstractmethod
    def generate_embedding(self, text: Union[str, List[str]]) -> Union[np.ndarray, List[float]]:
        """
        Generate embeddings for text(s)

        Args:
            text: Single text or list of texts

        Returns:
            Embedding vector(s) as numpy array or list of floats
        """
        pass

    @abstractmethod
    def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False
    ) -> List[Union[np.ndarray, List[float]]]:
        """
        Generate embeddings for a batch of texts

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get the dimension of embeddings

        Returns:
            Embedding dimension
        """
        pass

    def warmup(self):
        """
        Warmup the model with a dummy input
        """
        try:
            _ = self.generate_embedding("warmup text")
        except Exception:
            pass