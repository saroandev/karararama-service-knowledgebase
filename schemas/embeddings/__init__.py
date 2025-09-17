"""
Embedding schemas for various providers
"""

# Base embedding schemas
from schemas.embeddings.base import (
    EmbeddingProvider,
    EmbeddingModel,
    EmbeddingConfig,
    EmbeddingRequest,
    BatchEmbeddingRequest,
    EmbeddingResult,
    BatchEmbeddingResult,
    EmbeddingStats,
    EmbeddingComparison
)

# OpenAI embedding schemas
from schemas.embeddings.openai import (
    OpenAIEmbeddingModel,
    OpenAIEmbeddingConfig,
    OpenAIEmbeddingRequest,
    OpenAIEmbeddingResponse,
    OpenAIEmbeddingError,
    OpenAIUsageStats,
    OpenAIBatchEmbeddingJob
)

# Local embedding schemas
from schemas.embeddings.local import (
    LocalModelFramework,
    LocalEmbeddingModel,
    LocalEmbeddingConfig,
    LocalModelInfo,
    LocalEmbeddingRequest,
    LocalEmbeddingResult,
    LocalModelCache,
    LocalBenchmarkResult
)

__all__ = [
    # Base
    "EmbeddingProvider",
    "EmbeddingModel",
    "EmbeddingConfig",
    "EmbeddingRequest",
    "BatchEmbeddingRequest",
    "EmbeddingResult",
    "BatchEmbeddingResult",
    "EmbeddingStats",
    "EmbeddingComparison",
    # OpenAI
    "OpenAIEmbeddingModel",
    "OpenAIEmbeddingConfig",
    "OpenAIEmbeddingRequest",
    "OpenAIEmbeddingResponse",
    "OpenAIEmbeddingError",
    "OpenAIUsageStats",
    "OpenAIBatchEmbeddingJob",
    # Local
    "LocalModelFramework",
    "LocalEmbeddingModel",
    "LocalEmbeddingConfig",
    "LocalModelInfo",
    "LocalEmbeddingRequest",
    "LocalEmbeddingResult",
    "LocalModelCache",
    "LocalBenchmarkResult",
]


# Helper functions
def create_embedding_config(
    provider: str = "openai",
    model: str = None,
    dimension: int = 1536,
    api_key: str = None
) -> EmbeddingConfig:
    """
    Create embedding configuration based on provider

    Args:
        provider: Embedding provider (openai, local, etc.)
        model: Model name or path
        dimension: Embedding dimension
        api_key: API key if required

    Returns:
        Configured embedding config
    """
    if provider == "openai":
        from schemas.embeddings.openai import OpenAIEmbeddingConfig

        if not model:
            model = OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL

        if not api_key:
            raise ValueError("OpenAI provider requires api_key")

        return OpenAIEmbeddingConfig(
            model=model,
            dimension=dimension,
            api_key=api_key
        )

    elif provider == "local":
        from schemas.embeddings.local import LocalEmbeddingConfig

        if not model:
            model = LocalEmbeddingModel.ALL_MINILM_L6_V2
            dimension = 384  # Default for all-MiniLM-L6-v2

        return LocalEmbeddingConfig(
            model=model,
            dimension=dimension
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")


def get_model_dimension(provider: str, model: str) -> int:
    """
    Get the output dimension for a model

    Args:
        provider: Embedding provider
        model: Model name

    Returns:
        Output dimension
    """
    dimensions = {
        # OpenAI models
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        # Local models
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "multilingual-e5-small": 384,
        "multilingual-e5-base": 768,
        "multilingual-e5-large": 1024,
        "BAAI/bge-small-en-v1.5": 384,
        "BAAI/bge-base-en-v1.5": 768,
        "BAAI/bge-large-en-v1.5": 1024,
    }

    return dimensions.get(model, 768)  # Default to 768


def validate_embedding_dimension(embeddings: list, expected_dim: int) -> bool:
    """
    Validate that embeddings have the expected dimension

    Args:
        embeddings: List of embedding vectors
        expected_dim: Expected dimension

    Returns:
        True if all embeddings match expected dimension
    """
    if not embeddings:
        return False

    for embedding in embeddings:
        if len(embedding) != expected_dim:
            return False

    return True


def calculate_similarity(embedding1: list, embedding2: list) -> float:
    """
    Calculate cosine similarity between two embeddings

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Cosine similarity between -1 and 1
    """
    if len(embedding1) != len(embedding2):
        raise ValueError("Embeddings must have the same dimension")

    import math

    dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
    norm1 = math.sqrt(sum(a * a for a in embedding1))
    norm2 = math.sqrt(sum(b * b for b in embedding2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def batch_embeddings(texts: list, batch_size: int = 100) -> list:
    """
    Split texts into batches for processing

    Args:
        texts: List of texts to process
        batch_size: Size of each batch

    Returns:
        List of text batches
    """
    batches = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batches.append(batch)
    return batches


def normalize_embedding(embedding: list) -> list:
    """
    Normalize an embedding vector to unit length

    Args:
        embedding: Embedding vector

    Returns:
        Normalized embedding
    """
    import math

    norm = math.sqrt(sum(x * x for x in embedding))
    if norm == 0:
        return embedding
    return [x / norm for x in embedding]