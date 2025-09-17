"""
Language model generation schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal, Union
from datetime import datetime
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    AZURE = "azure"


class LLMModel(str, Enum):
    """Common LLM models"""
    # OpenAI models
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4 = "gpt-4"
    GPT_35_TURBO = "gpt-3.5-turbo"

    # Anthropic models
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_HAIKU = "claude-3-haiku"

    # Google models
    GEMINI_PRO = "gemini-pro"
    GEMINI_PRO_VISION = "gemini-pro-vision"
    PALM_2 = "palm-2"

    # Open models
    LLAMA_2_70B = "llama-2-70b"
    LLAMA_2_13B = "llama-2-13b"
    LLAMA_2_7B = "llama-2-7b"
    MISTRAL_7B = "mistral-7b"
    MIXTRAL_8X7B = "mixtral-8x7b"


class LLMConfig(BaseModel):
    """Configuration for LLM generation"""
    provider: LLMProvider = Field(..., description="LLM provider")
    model: str = Field(..., description="Model name or identifier")

    # API settings
    api_key: Optional[str] = Field(default=None, description="API key")
    api_base_url: Optional[str] = Field(default=None, description="API base URL")
    api_version: Optional[str] = Field(default=None, description="API version")
    organization: Optional[str] = Field(default=None, description="Organization ID")

    # Generation parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=1000, ge=1, description="Maximum tokens to generate")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Presence penalty")

    # Advanced parameters
    n: int = Field(default=1, ge=1, le=10, description="Number of completions")
    stream: bool = Field(default=False, description="Stream responses")
    stop_sequences: Optional[List[str]] = Field(default=None, description="Stop sequences")
    logit_bias: Optional[Dict[str, float]] = Field(default=None, description="Token logit bias")

    # Rate limiting
    max_retries: int = Field(default=3, ge=0, description="Max retry attempts")
    timeout_seconds: int = Field(default=60, ge=1, description="Request timeout")
    rate_limit_rpm: Optional[int] = Field(default=None, ge=1, description="Requests per minute limit")

    # Cost tracking
    cost_per_1k_input_tokens: Optional[float] = Field(default=None, ge=0, description="Input token cost")
    cost_per_1k_output_tokens: Optional[float] = Field(default=None, ge=0, description="Output token cost")

    @validator("temperature")
    def validate_temperature(cls, v, values):
        """Validate temperature based on provider"""
        if "provider" in values and values["provider"] == LLMProvider.OPENAI:
            if v < 0 or v > 2:
                raise ValueError("OpenAI temperature must be between 0 and 2")
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class GenerationRequest(BaseModel):
    """Request for text generation"""
    prompt: Optional[str] = Field(default=None, description="Text prompt (for completion models)")
    messages: Optional[List[Dict[str, str]]] = Field(default=None, description="Chat messages")

    # Context
    system_prompt: Optional[str] = Field(default=None, description="System prompt")
    context: Optional[str] = Field(default=None, description="Additional context")
    examples: Optional[List[Dict[str, str]]] = Field(default=None, description="Few-shot examples")

    # Generation parameters (override config)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Temperature override")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Max tokens override")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p override")

    # Options
    return_metadata: bool = Field(default=True, description="Return generation metadata")
    return_logprobs: bool = Field(default=False, description="Return token log probabilities")
    echo: bool = Field(default=False, description="Echo the prompt in response")

    # Metadata
    user_id: Optional[str] = Field(default=None, description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    request_id: Optional[str] = Field(default=None, description="Request identifier")

    @validator("messages")
    def validate_input(cls, v, values):
        """Ensure either prompt or messages is provided"""
        if not v and not values.get("prompt"):
            raise ValueError("Either prompt or messages must be provided")
        if v and values.get("prompt"):
            raise ValueError("Cannot provide both prompt and messages")
        return v

    class Config:
        validate_assignment = True


class GenerationResponse(BaseModel):
    """Response from text generation"""
    text: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used")
    provider: LLMProvider = Field(..., description="Provider used")

    # Token usage
    prompt_tokens: int = Field(..., ge=0, description="Input token count")
    completion_tokens: int = Field(..., ge=0, description="Generated token count")
    total_tokens: int = Field(..., ge=0, description="Total token count")

    # Generation metadata
    finish_reason: Optional[str] = Field(default=None, description="Stop reason")
    generation_time_ms: float = Field(..., ge=0, description="Generation time")

    # Additional choices (for n > 1)
    choices: Optional[List[Dict[str, Any]]] = Field(default=None, description="Multiple completions")
    best_of: Optional[int] = Field(default=None, description="Best of N sampling")

    # Log probabilities
    logprobs: Optional[Dict[str, Any]] = Field(default=None, description="Token log probabilities")

    # Cost estimation
    estimated_cost: Optional[float] = Field(default=None, ge=0, description="Estimated cost in USD")

    # Metadata
    request_id: Optional[str] = Field(default=None, description="Request identifier")
    created_at: datetime = Field(default_factory=datetime.now, description="Response timestamp")

    @validator("total_tokens", always=True)
    def calculate_total_tokens(cls, v, values):
        """Calculate total tokens"""
        if "prompt_tokens" in values and "completion_tokens" in values:
            return values["prompt_tokens"] + values["completion_tokens"]
        return v or 0

    class Config:
        use_enum_values = True
        validate_assignment = True


class ChatMessage(BaseModel):
    """Single chat message"""
    role: Literal["system", "user", "assistant", "function"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")

    # Optional fields
    name: Optional[str] = Field(default=None, description="Name of sender")
    function_call: Optional[Dict[str, Any]] = Field(default=None, description="Function call")

    # Metadata
    timestamp: Optional[datetime] = Field(default=None, description="Message timestamp")
    token_count: Optional[int] = Field(default=None, ge=0, description="Token count")

    class Config:
        validate_assignment = True


class ChatCompletionRequest(BaseModel):
    """Request for chat completion"""
    messages: List[ChatMessage] = Field(..., min_items=1, description="Chat messages")
    model: str = Field(..., description="Model to use")

    # Generation parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=1000, ge=1, description="Max tokens")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p sampling")

    # Chat-specific parameters
    functions: Optional[List[Dict[str, Any]]] = Field(default=None, description="Available functions")
    function_call: Optional[Union[str, Dict[str, str]]] = Field(default=None, description="Function calling mode")
    response_format: Optional[Dict[str, str]] = Field(default=None, description="Response format")

    # Options
    stream: bool = Field(default=False, description="Stream responses")
    user: Optional[str] = Field(default=None, description="User identifier")

    @validator("messages")
    def validate_messages(cls, v):
        """Validate message structure"""
        has_user_message = any(msg.role == "user" for msg in v)
        if not has_user_message:
            raise ValueError("Messages must contain at least one user message")
        return v

    class Config:
        validate_assignment = True


class StreamChunk(BaseModel):
    """Single chunk in streaming response"""
    delta: str = Field(..., description="Text delta")
    index: int = Field(..., ge=0, description="Chunk index")

    # Metadata
    finish_reason: Optional[str] = Field(default=None, description="Stop reason if final chunk")
    logprobs: Optional[Dict[str, Any]] = Field(default=None, description="Log probabilities")

    # Timing
    timestamp: datetime = Field(default_factory=datetime.now, description="Chunk timestamp")

    class Config:
        validate_assignment = True


class BatchGenerationRequest(BaseModel):
    """Request for batch generation"""
    prompts: List[str] = Field(..., min_items=1, description="List of prompts")
    model: str = Field(..., description="Model to use")

    # Batch settings
    batch_size: int = Field(default=10, ge=1, description="Batch size for processing")
    parallel: bool = Field(default=True, description="Process in parallel")

    # Common parameters for all prompts
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=1000, ge=1, description="Max tokens per prompt")

    # Options
    stop_on_error: bool = Field(default=False, description="Stop batch on first error")
    return_failures: bool = Field(default=True, description="Return failed generations")

    class Config:
        validate_assignment = True


class BatchGenerationResponse(BaseModel):
    """Response from batch generation"""
    results: List[GenerationResponse] = Field(..., description="Generation results")
    total_prompts: int = Field(..., ge=1, description="Total prompts processed")

    # Statistics
    successful: int = Field(..., ge=0, description="Successful generations")
    failed: int = Field(default=0, ge=0, description="Failed generations")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")

    # Performance
    total_time_ms: float = Field(..., ge=0, description="Total processing time")
    avg_time_per_prompt_ms: float = Field(..., ge=0, description="Average time per prompt")

    # Token usage
    total_prompt_tokens: int = Field(..., ge=0, description="Total input tokens")
    total_completion_tokens: int = Field(..., ge=0, description="Total output tokens")

    # Cost
    total_estimated_cost: Optional[float] = Field(default=None, ge=0, description="Total cost estimate")

    @validator("failed", always=True)
    def calculate_failed(cls, v, values):
        """Calculate failed count"""
        if "total_prompts" in values and "successful" in values:
            return values["total_prompts"] - values["successful"]
        return v or 0

    class Config:
        validate_assignment = True


class LLMMetrics(BaseModel):
    """Metrics for LLM usage"""
    provider: LLMProvider = Field(..., description="Provider")
    model: str = Field(..., description="Model")

    # Usage metrics
    total_requests: int = Field(..., ge=0, description="Total requests")
    successful_requests: int = Field(..., ge=0, description="Successful requests")
    failed_requests: int = Field(default=0, ge=0, description="Failed requests")

    # Token metrics
    total_prompt_tokens: int = Field(..., ge=0, description="Total input tokens")
    total_completion_tokens: int = Field(..., ge=0, description="Total output tokens")
    avg_prompt_length: float = Field(..., ge=0, description="Average prompt length")
    avg_completion_length: float = Field(..., ge=0, description="Average completion length")

    # Performance metrics
    avg_latency_ms: float = Field(..., ge=0, description="Average latency")
    p50_latency_ms: float = Field(..., ge=0, description="Median latency")
    p95_latency_ms: float = Field(..., ge=0, description="95th percentile latency")
    p99_latency_ms: float = Field(..., ge=0, description="99th percentile latency")

    # Cost metrics
    total_cost_usd: float = Field(..., ge=0, description="Total cost in USD")
    avg_cost_per_request: float = Field(..., ge=0, description="Average cost per request")

    # Error tracking
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Error rate")
    timeout_count: int = Field(default=0, ge=0, description="Timeout count")
    rate_limit_hits: int = Field(default=0, ge=0, description="Rate limit hits")

    # Time period
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")

    @validator("error_rate", always=True)
    def calculate_error_rate(cls, v, values):
        """Calculate error rate"""
        if "total_requests" in values and values["total_requests"] > 0:
            failed = values.get("failed_requests", 0)
            return failed / values["total_requests"]
        return v or 0.0

    class Config:
        use_enum_values = True
        validate_assignment = True


class LLMCache(BaseModel):
    """Configuration for LLM response caching"""
    enabled: bool = Field(default=True, description="Enable caching")
    ttl_seconds: int = Field(default=3600, ge=1, description="Cache TTL")

    # Cache key strategy
    include_model: bool = Field(default=True, description="Include model in cache key")
    include_temperature: bool = Field(default=True, description="Include temperature in cache key")
    include_system_prompt: bool = Field(default=False, description="Include system prompt in cache key")

    # Cache size limits
    max_entries: int = Field(default=1000, ge=1, description="Maximum cache entries")
    max_size_mb: int = Field(default=100, ge=1, description="Maximum cache size in MB")

    # Cache statistics
    hits: int = Field(default=0, ge=0, description="Cache hits")
    misses: int = Field(default=0, ge=0, description="Cache misses")
    evictions: int = Field(default=0, ge=0, description="Cache evictions")

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    class Config:
        validate_assignment = True