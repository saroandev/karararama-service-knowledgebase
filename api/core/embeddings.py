"""
Embedding generation utilities
"""
import logging
from typing import List
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings"""

    def __init__(self):
        self.client = None
        if settings.LLM_PROVIDER == 'openai':
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not self.client:
            raise ValueError("Embedding client not initialized")

        try:
            response = self.client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 20) -> List[List[float]]:
        """Generate embeddings for multiple texts in batches"""
        if not self.client:
            raise ValueError("Embedding client not initialized")

        embeddings = []
        for batch_start in range(0, len(texts), batch_size):
            batch_end = min(batch_start + batch_size, len(texts))
            batch_texts = texts[batch_start:batch_end]

            try:
                response = self.client.embeddings.create(
                    model=settings.EMBEDDING_MODEL,
                    input=batch_texts
                )
                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)
                logger.info(f"Processed {batch_end}/{len(texts)} embeddings")
            except Exception as e:
                logger.error(f"Batch embedding generation failed: {e}")
                raise

        return embeddings


# Singleton instance
embedding_service = EmbeddingService()