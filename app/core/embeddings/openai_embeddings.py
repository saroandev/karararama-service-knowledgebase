"""
OpenAI embedding implementation
"""
import logging
from typing import List, Union, Optional
import numpy as np
from openai import OpenAI

from app.core.embeddings.base import AbstractEmbedding
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIEmbedding(AbstractEmbedding):
    """OpenAI embedding implementation using text-embedding models"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        batch_size: int = 20
    ):
        """
        Initialize OpenAI embedding generator

        Args:
            api_key: OpenAI API key (uses settings if not provided)
            model_name: Model name (default: text-embedding-3-small)
            batch_size: Batch size for processing multiple texts
        """
        model_name = model_name or settings.EMBEDDING_MODEL or "text-embedding-3-small"
        super().__init__(model_name)

        self.api_key = api_key or settings.OPENAI_API_KEY
        self.batch_size = batch_size

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

        # Set dimension based on model
        if "text-embedding-3-small" in self.model_name:
            self.dimension = 1536
        elif "text-embedding-3-large" in self.model_name:
            self.dimension = 3072
        elif "text-embedding-ada-002" in self.model_name:
            self.dimension = 1536
        else:
            # Default dimension, will be updated after first embedding
            self.dimension = 1536

        logger.info(f"Initialized OpenAI embeddings with model: {self.model_name}, dimension: {self.dimension}")

    def generate_embedding(self, text: Union[str, List[str]]) -> Union[np.ndarray, List[float]]:
        """
        Generate embeddings for text(s)

        Args:
            text: Single text or list of texts

        Returns:
            Embedding vector(s) as numpy array or list of floats
        """
        if isinstance(text, str):
            text = [text]
            single_input = True
        else:
            single_input = False

        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=text
            )

            embeddings = [data.embedding for data in response.data]

            # Update dimension if not set correctly
            if embeddings and len(embeddings[0]) != self.dimension:
                self.dimension = len(embeddings[0])
                logger.info(f"Updated embedding dimension to: {self.dimension}")

            if single_input:
                return embeddings[0]
            return embeddings

        except Exception as e:
            logger.error(f"Error generating OpenAI embeddings: {e}")
            raise

    def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing (uses instance default if not provided)
            show_progress: Whether to show progress (logs info for OpenAI)

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        batch_size = batch_size or self.batch_size
        embeddings = []

        for batch_start in range(0, len(texts), batch_size):
            batch_end = min(batch_start + batch_size, len(texts))
            batch_texts = texts[batch_start:batch_end]

            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=batch_texts
                )

                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)

                if show_progress:
                    logger.info(f"Processed {batch_end}/{len(texts)} embeddings")

            except Exception as e:
                logger.error(f"Batch embedding generation failed at batch {batch_start}-{batch_end}: {e}")
                raise

        return embeddings

    def get_dimension(self) -> int:
        """
        Get the dimension of embeddings

        Returns:
            Embedding dimension
        """
        return self.dimension