"""
Base embedding schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class EmbeddingProvider(str, Enum):
    """Supported embedding providers"""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    COHERE = "cohere"
    LOCAL = "local"


class EmbeddingModel(str, Enum):
    """Common embedding models"""
    # OpenAI models
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"

    # Sentence Transformers models
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"
    MULTILINGUAL_E5_SMALL = "multilingual-e5-small"
    MULTILINGUAL_E5_BASE = "multilingual-e5-base"
    MULTILINGUAL_E5_LARGE = "multilingual-e5-large"

    # Cohere models
    EMBED_ENGLISH_V3 = "embed-english-v3.0"
    EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0"


class EmbeddingConfig(BaseModel):
    """Base configuration for embedding generation"""
    provider: EmbeddingProvider = Field(..., description="Embedding provider")
    model: str = Field(..., description="Model name or path")

    # Model parameters
    dimension: int = Field(..., ge=1, le=4096, description="Embedding dimension")
    max_tokens: int = Field(default=8192, ge=1, description="Maximum input tokens")

    # Batch processing
    batch_size: int = Field(default=100, ge=1, le=2048, description="Batch size for processing")
    max_retries: int = Field(default=3, ge=0, description="Max retries on failure")

    # Performance settings
    use_cache: bool = Field(default=True, description="Use embedding cache")
    parallel_workers: int = Field(default=1, ge=1, description="Number of parallel workers")

    # API settings (if applicable)
    api_key: Optional[str] = Field(default=None, description="API key for provider")
    api_base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    timeout_seconds: int = Field(default=30, ge=1, description="API timeout in seconds")

    # Model loading (for local models)
    model_path: Optional[str] = Field(default=None, description="Path to local model")
    device: str = Field(default="cpu", description="Device to run model on (cpu/cuda/mps)")
    quantization: Optional[str] = Field(default=None, description="Quantization method")

    @validator("dimension")
    def validate_dimension(cls, v, values):
        """Validate dimension matches model requirements"""
        if "model" in values:
            model = values["model"]
            # OpenAI models
            if model == "text-embedding-3-small" and v != 1536:
                raise ValueError(f"{model} requires dimension=1536")
            elif model == "text-embedding-3-large" and v != 3072:
                raise ValueError(f"{model} requires dimension=3072")
            elif model == "text-embedding-ada-002" and v != 1536:
                raise ValueError(f"{model} requires dimension=1536")
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class EmbeddingRequest(BaseModel):
    """Request for embedding generation"""
    text: str = Field(..., min_length=1, description="Text to embed")

    # Optional parameters
    model_override: Optional[str] = Field(default=None, description="Override default model")
    truncate: bool = Field(default=True, description="Truncate if exceeds max tokens")
    normalize: bool = Field(default=True, description="Normalize embeddings")

    # Metadata
    document_id: Optional[str] = Field(default=None, description="Associated document ID")
    chunk_id: Optional[str] = Field(default=None, description="Associated chunk ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        validate_assignment = True


class BatchEmbeddingRequest(BaseModel):
    """Request for batch embedding generation"""
    texts: List[str] = Field(..., min_items=1, description="Texts to embed")

    # Processing options
    model_override: Optional[str] = Field(default=None, description="Override default model")
    truncate: bool = Field(default=True, description="Truncate if exceeds max tokens")
    normalize: bool = Field(default=True, description="Normalize embeddings")

    # Batch options
    batch_size: Optional[int] = Field(default=None, ge=1, description="Override default batch size")
    parallel: bool = Field(default=False, description="Process in parallel")

    # Metadata
    document_id: Optional[str] = Field(default=None, description="Associated document ID")
    chunk_ids: Optional[List[str]] = Field(default=None, description="Associated chunk IDs")

    @validator("chunk_ids")
    def validate_chunk_ids(cls, v, values):
        """Ensure chunk_ids matches texts length if provided"""
        if v and "texts" in values and len(v) != len(values["texts"]):
            raise ValueError("chunk_ids must match texts length")
        return v

    class Config:
        validate_assignment = True


class EmbeddingResult(BaseModel):
    """Result from embedding generation"""
    embedding: List[float] = Field(..., description="Generated embedding vector")
    dimension: int = Field(..., ge=1, description="Embedding dimension")

    # Model information
    model: str = Field(..., description="Model used")
    provider: EmbeddingProvider = Field(..., description="Provider used")

    # Processing information
    token_count: int = Field(..., ge=0, description="Number of tokens processed")
    truncated: bool = Field(default=False, description="Whether text was truncated")

    # Performance metrics
    processing_time_ms: float = Field(..., ge=0, description="Processing time in milliseconds")
    from_cache: bool = Field(default=False, description="Whether from cache")

    # Metadata
    text_hash: Optional[str] = Field(default=None, description="Hash of input text")
    timestamp: datetime = Field(default_factory=datetime.now, description="Generation timestamp")

    @validator("dimension", always=True)
    def calculate_dimension(cls, v, values):
        """Calculate dimension from embedding if not provided"""
        if "embedding" in values and values["embedding"]:
            return len(values["embedding"])
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class BatchEmbeddingResult(BaseModel):
    """Result from batch embedding generation"""
    embeddings: List[List[float]] = Field(..., description="Generated embedding vectors")
    dimension: int = Field(..., ge=1, description="Embedding dimension")

    # Model information
    model: str = Field(..., description="Model used")
    provider: EmbeddingProvider = Field(..., description="Provider used")

    # Processing statistics
    total_texts: int = Field(..., ge=1, description="Total number of texts")
    successful: int = Field(..., ge=0, description="Number of successful embeddings")
    failed: int = Field(default=0, ge=0, description="Number of failed embeddings")

    # Performance metrics
    total_tokens: int = Field(..., ge=0, description="Total tokens processed")
    processing_time_ms: float = Field(..., ge=0, description="Total processing time")
    avg_time_per_text_ms: float = Field(..., ge=0, description="Average time per text")

    # Error information
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details for failed texts")

    @validator("dimension", always=True)
    def calculate_dimension(cls, v, values):
        """Calculate dimension from first embedding if not provided"""
        if "embeddings" in values and values["embeddings"] and values["embeddings"][0]:
            return len(values["embeddings"][0])
        return v

    @validator("avg_time_per_text_ms", always=True)
    def calculate_avg_time(cls, v, values):
        """Calculate average time per text"""
        if "processing_time_ms" in values and "total_texts" in values and values["total_texts"] > 0:
            return values["processing_time_ms"] / values["total_texts"]
        return v or 0

    class Config:
        use_enum_values = True
        validate_assignment = True


class EmbeddingStats(BaseModel):
    """Statistics for embedding operations"""
    provider: EmbeddingProvider = Field(..., description="Embedding provider")
    model: str = Field(..., description="Model name")

    # Usage metrics
    total_embeddings: int = Field(..., ge=0, description="Total embeddings generated")
    total_tokens: int = Field(..., ge=0, description="Total tokens processed")
    total_texts: int = Field(..., ge=0, description="Total texts processed")

    # Performance metrics
    avg_processing_time_ms: float = Field(..., ge=0, description="Average processing time")
    min_processing_time_ms: float = Field(..., ge=0, description="Minimum processing time")
    max_processing_time_ms: float = Field(..., ge=0, description="Maximum processing time")

    # Cache metrics
    cache_hits: int = Field(default=0, ge=0, description="Number of cache hits")
    cache_misses: int = Field(default=0, ge=0, description="Number of cache misses")
    cache_hit_rate: float = Field(default=0, ge=0, le=1, description="Cache hit rate")

    # Error metrics
    total_errors: int = Field(default=0, ge=0, description="Total errors")
    error_rate: float = Field(default=0, ge=0, le=1, description="Error rate")

    # Cost estimation (for paid APIs)
    estimated_cost: Optional[float] = Field(default=None, ge=0, description="Estimated cost in USD")

    # Time period
    period_start: datetime = Field(..., description="Stats period start")
    period_end: datetime = Field(..., description="Stats period end")

    @validator("cache_hit_rate", always=True)
    def calculate_hit_rate(cls, v, values):
        """Calculate cache hit rate"""
        hits = values.get("cache_hits", 0)
        misses = values.get("cache_misses", 0)
        total = hits + misses
        if total > 0:
            return hits / total
        return 0

    @validator("error_rate", always=True)
    def calculate_error_rate(cls, v, values):
        """Calculate error rate"""
        errors = values.get("total_errors", 0)
        total = values.get("total_texts", 0)
        if total > 0:
            return errors / total
        return 0

    class Config:
        use_enum_values = True
        validate_assignment = True


class EmbeddingComparison(BaseModel):
    """Comparison between two embeddings"""
    embedding1: List[float] = Field(..., description="First embedding")
    embedding2: List[float] = Field(..., description="Second embedding")

    # Similarity metrics
    cosine_similarity: float = Field(..., ge=-1, le=1, description="Cosine similarity")
    euclidean_distance: float = Field(..., ge=0, description="Euclidean distance")
    dot_product: float = Field(..., description="Dot product")

    # Additional metrics
    manhattan_distance: Optional[float] = Field(default=None, ge=0, description="Manhattan distance")
    minkowski_distance: Optional[float] = Field(default=None, ge=0, description="Minkowski distance")

    # Metadata
    metadata1: Optional[Dict[str, Any]] = Field(default=None, description="Metadata for embedding1")
    metadata2: Optional[Dict[str, Any]] = Field(default=None, description="Metadata for embedding2")

    @validator("embedding2")
    def validate_dimensions(cls, v, values):
        """Ensure embeddings have same dimension"""
        if "embedding1" in values and len(v) != len(values["embedding1"]):
            raise ValueError("Embeddings must have the same dimension")
        return v

    class Config:
        validate_assignment = True