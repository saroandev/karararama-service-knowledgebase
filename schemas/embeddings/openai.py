"""
OpenAI embedding provider schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

from schemas.embeddings.base import EmbeddingConfig, EmbeddingProvider


class OpenAIEmbeddingModel(str):
    """OpenAI embedding models with dimensions"""
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"  # 1536 dimensions
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"  # 3072 dimensions
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"  # 1536 dimensions


class OpenAIEmbeddingConfig(EmbeddingConfig):
    """Configuration for OpenAI embeddings"""
    provider: Literal[EmbeddingProvider.OPENAI] = Field(
        default=EmbeddingProvider.OPENAI,
        description="Provider type (always OpenAI)"
    )

    # OpenAI specific settings
    model: str = Field(
        default=OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL,
        description="OpenAI model name"
    )
    api_key: str = Field(..., description="OpenAI API key")
    organization: Optional[str] = Field(default=None, description="OpenAI organization ID")

    # Model-specific dimensions
    dimension: int = Field(default=1536, description="Embedding dimension")

    # API settings
    api_base_url: Optional[str] = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL"
    )
    api_version: Optional[str] = Field(default=None, description="API version")

    # Rate limiting
    max_requests_per_minute: int = Field(default=3000, ge=1, description="Max RPM")
    max_tokens_per_minute: int = Field(default=1000000, ge=1, description="Max TPM")

    # Advanced settings
    encoding_format: Literal["float", "base64"] = Field(
        default="float",
        description="Encoding format for embeddings"
    )
    user: Optional[str] = Field(default=None, description="Unique user identifier")

    @validator("dimension")
    def validate_dimension_for_model(cls, v, values):
        """Validate dimension matches OpenAI model requirements"""
        if "model" in values:
            model = values["model"]
            if model == OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL:
                if v != 1536:
                    raise ValueError(f"{model} requires dimension=1536")
            elif model == OpenAIEmbeddingModel.TEXT_EMBEDDING_3_LARGE:
                if v != 3072:
                    raise ValueError(f"{model} requires dimension=3072")
            elif model == OpenAIEmbeddingModel.TEXT_EMBEDDING_ADA_002:
                if v != 1536:
                    raise ValueError(f"{model} requires dimension=1536")
        return v

    @validator("api_key")
    def validate_api_key(cls, v):
        """Validate API key format"""
        if not v.startswith("sk-"):
            raise ValueError("OpenAI API key must start with 'sk-'")
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class OpenAIEmbeddingRequest(BaseModel):
    """Request for OpenAI embedding generation"""
    input: str | List[str] = Field(..., description="Text or list of texts to embed")
    model: str = Field(
        default=OpenAIEmbeddingModel.TEXT_EMBEDDING_3_SMALL,
        description="Model to use"
    )

    # Optional parameters
    encoding_format: Literal["float", "base64"] = Field(
        default="float",
        description="Format for encoding embeddings"
    )
    user: Optional[str] = Field(default=None, description="Unique user identifier for tracking")

    # Custom parameters (not sent to API)
    truncate: bool = Field(default=True, description="Truncate if exceeds max tokens")
    show_progress: bool = Field(default=False, description="Show progress for batch processing")

    @validator("input")
    def validate_input(cls, v):
        """Validate input is not empty"""
        if isinstance(v, str) and not v.strip():
            raise ValueError("Input text cannot be empty")
        elif isinstance(v, list) and (not v or any(not text.strip() for text in v)):
            raise ValueError("Input texts cannot be empty")
        return v

    class Config:
        validate_assignment = True


class OpenAIEmbeddingResponse(BaseModel):
    """Response from OpenAI embedding API"""
    object: Literal["list"] = Field(..., description="Object type")
    data: List[Dict[str, Any]] = Field(..., description="Embedding data")
    model: str = Field(..., description="Model used")
    usage: Dict[str, int] = Field(..., description="Token usage information")

    # Parsed fields
    embeddings: Optional[List[List[float]]] = Field(default=None, description="Parsed embeddings")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens used")

    @validator("embeddings", always=True)
    def parse_embeddings(cls, v, values):
        """Parse embeddings from data field"""
        if not v and "data" in values:
            embeddings = []
            for item in values["data"]:
                if "embedding" in item:
                    embeddings.append(item["embedding"])
            return embeddings if embeddings else None
        return v

    @validator("total_tokens", always=True)
    def parse_total_tokens(cls, v, values):
        """Parse total tokens from usage field"""
        if not v and "usage" in values:
            return values["usage"].get("total_tokens")
        return v

    class Config:
        validate_assignment = True


class OpenAIEmbeddingError(BaseModel):
    """Error response from OpenAI API"""
    error: Dict[str, Any] = Field(..., description="Error details")

    # Parsed fields
    message: Optional[str] = Field(default=None, description="Error message")
    type: Optional[str] = Field(default=None, description="Error type")
    code: Optional[str] = Field(default=None, description="Error code")

    @validator("message", always=True)
    def parse_message(cls, v, values):
        """Parse message from error field"""
        if not v and "error" in values:
            return values["error"].get("message")
        return v

    @validator("type", always=True)
    def parse_type(cls, v, values):
        """Parse type from error field"""
        if not v and "error" in values:
            return values["error"].get("type")
        return v

    @validator("code", always=True)
    def parse_code(cls, v, values):
        """Parse code from error field"""
        if not v and "error" in values:
            return values["error"].get("code")
        return v

    class Config:
        validate_assignment = True


class OpenAIUsageStats(BaseModel):
    """Usage statistics for OpenAI embeddings"""
    # Token usage
    prompt_tokens: int = Field(..., ge=0, description="Total prompt tokens used")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")

    # Request counts
    total_requests: int = Field(..., ge=0, description="Total API requests made")
    successful_requests: int = Field(..., ge=0, description="Successful requests")
    failed_requests: int = Field(default=0, ge=0, description="Failed requests")

    # Rate limit tracking
    requests_this_minute: int = Field(default=0, ge=0, description="Requests in current minute")
    tokens_this_minute: int = Field(default=0, ge=0, description="Tokens in current minute")

    # Cost estimation
    estimated_cost_usd: float = Field(..., ge=0, description="Estimated cost in USD")
    cost_per_1k_tokens: float = Field(
        default=0.00002,  # Default for text-embedding-3-small
        description="Cost per 1K tokens"
    )

    # Time tracking
    period_start: datetime = Field(..., description="Stats period start")
    period_end: datetime = Field(..., description="Stats period end")
    last_request_time: Optional[datetime] = Field(default=None, description="Last request timestamp")

    @validator("estimated_cost_usd", always=True)
    def calculate_cost(cls, v, values):
        """Calculate estimated cost based on tokens"""
        if "total_tokens" in values and "cost_per_1k_tokens" in values:
            return (values["total_tokens"] / 1000) * values["cost_per_1k_tokens"]
        return v or 0

    class Config:
        validate_assignment = True


class OpenAIBatchEmbeddingJob(BaseModel):
    """Batch embedding job for OpenAI"""
    job_id: str = Field(..., description="Unique job identifier")
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        ..., description="Job status"
    )

    # Input information
    total_texts: int = Field(..., ge=1, description="Total number of texts")
    batch_size: int = Field(..., ge=1, description="Batch size")
    total_batches: int = Field(..., ge=1, description="Total number of batches")

    # Progress tracking
    processed_batches: int = Field(default=0, ge=0, description="Processed batches")
    processed_texts: int = Field(default=0, ge=0, description="Processed texts")
    failed_texts: int = Field(default=0, ge=0, description="Failed texts")

    # Results
    embeddings: Optional[List[List[float]]] = Field(default=None, description="Generated embeddings")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Errors for failed texts")

    # Performance
    start_time: datetime = Field(default_factory=datetime.now, description="Job start time")
    end_time: Optional[datetime] = Field(default=None, description="Job end time")
    total_tokens_used: int = Field(default=0, ge=0, description="Total tokens used")

    @validator("total_batches", always=True)
    def calculate_batches(cls, v, values):
        """Calculate total batches from texts and batch size"""
        if "total_texts" in values and "batch_size" in values:
            import math
            return math.ceil(values["total_texts"] / values["batch_size"])
        return v

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage"""
        if self.total_texts > 0:
            return (self.processed_texts / self.total_texts) * 100
        return 0

    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Estimate remaining time in seconds"""
        if self.processed_texts > 0 and self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            rate = self.processed_texts / elapsed
            remaining_texts = self.total_texts - self.processed_texts
            if rate > 0:
                return remaining_texts / rate
        return None

    class Config:
        validate_assignment = True