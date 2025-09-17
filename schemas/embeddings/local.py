"""
Local embedding provider schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum

from schemas.embeddings.base import EmbeddingConfig, EmbeddingProvider


class LocalModelFramework(str, Enum):
    """Supported local model frameworks"""
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    HUGGINGFACE = "huggingface"
    ONNX = "onnx"
    TENSORFLOW = "tensorflow"
    PYTORCH = "pytorch"


class LocalEmbeddingModel(str):
    """Common local embedding models"""
    # Sentence Transformers models
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"  # 384 dimensions
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"  # 768 dimensions
    MULTILINGUAL_E5_SMALL = "multilingual-e5-small"  # 384 dimensions
    MULTILINGUAL_E5_BASE = "multilingual-e5-base"  # 768 dimensions
    MULTILINGUAL_E5_LARGE = "multilingual-e5-large"  # 1024 dimensions
    BGE_SMALL_EN_V1_5 = "BAAI/bge-small-en-v1.5"  # 384 dimensions
    BGE_BASE_EN_V1_5 = "BAAI/bge-base-en-v1.5"  # 768 dimensions
    BGE_LARGE_EN_V1_5 = "BAAI/bge-large-en-v1.5"  # 1024 dimensions


class LocalEmbeddingConfig(EmbeddingConfig):
    """Configuration for local embeddings"""
    provider: Literal[EmbeddingProvider.LOCAL] = Field(
        default=EmbeddingProvider.LOCAL,
        description="Provider type (always LOCAL)"
    )

    # Model configuration
    framework: LocalModelFramework = Field(
        default=LocalModelFramework.SENTENCE_TRANSFORMERS,
        description="Model framework"
    )
    model: str = Field(..., description="Model name or path")
    model_path: Optional[str] = Field(default=None, description="Local path to model files")

    # Hardware configuration
    device: str = Field(default="cpu", description="Device to run on (cpu/cuda/mps)")
    device_id: Optional[int] = Field(default=None, ge=0, description="GPU device ID")
    use_fp16: bool = Field(default=False, description="Use half precision")
    use_quantization: bool = Field(default=False, description="Use quantized model")

    # Model loading
    cache_dir: Optional[str] = Field(default=None, description="Cache directory for models")
    trust_remote_code: bool = Field(default=False, description="Trust remote code from HuggingFace")
    offline_mode: bool = Field(default=False, description="Run in offline mode")

    # Performance settings
    num_threads: Optional[int] = Field(default=None, ge=1, description="Number of CPU threads")
    batch_size: int = Field(default=32, ge=1, description="Batch size for inference")
    max_seq_length: int = Field(default=512, ge=1, description="Maximum sequence length")

    # Memory management
    low_memory: bool = Field(default=False, description="Use low memory mode")
    clear_cache_after_batch: bool = Field(default=False, description="Clear cache after each batch")

    # Model-specific parameters
    normalize_embeddings: bool = Field(default=True, description="Normalize output embeddings")
    pooling_method: Literal["mean", "max", "cls", "weighted_mean"] = Field(
        default="mean",
        description="Pooling method for token embeddings"
    )

    @validator("dimension")
    def validate_dimension_for_model(cls, v, values):
        """Validate dimension matches local model requirements"""
        if "model" in values:
            model = values["model"]
            # Common model dimensions
            model_dims = {
                "all-MiniLM-L6-v2": 384,
                "all-mpnet-base-v2": 768,
                "multilingual-e5-small": 384,
                "multilingual-e5-base": 768,
                "multilingual-e5-large": 1024,
                "BAAI/bge-small-en-v1.5": 384,
                "BAAI/bge-base-en-v1.5": 768,
                "BAAI/bge-large-en-v1.5": 1024,
            }
            if model in model_dims and v != model_dims[model]:
                raise ValueError(f"{model} outputs {model_dims[model]} dimensions, not {v}")
        return v

    @validator("device")
    def validate_device(cls, v):
        """Validate device is supported"""
        valid_devices = ["cpu", "cuda", "mps", "cuda:0", "cuda:1", "cuda:2", "cuda:3"]
        if not any(v.startswith(d) for d in ["cpu", "cuda", "mps"]):
            raise ValueError(f"Device must be one of: cpu, cuda, mps, or cuda:N")
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class LocalModelInfo(BaseModel):
    """Information about loaded local model"""
    model_name: str = Field(..., description="Model name or path")
    framework: LocalModelFramework = Field(..., description="Framework used")

    # Model properties
    dimension: int = Field(..., ge=1, description="Output dimension")
    max_seq_length: int = Field(..., ge=1, description="Maximum sequence length")
    vocab_size: Optional[int] = Field(default=None, ge=1, description="Vocabulary size")

    # Hardware info
    device: str = Field(..., description="Device model is loaded on")
    dtype: str = Field(..., description="Data type (float32/float16/int8)")
    memory_usage_mb: Optional[float] = Field(default=None, ge=0, description="Memory usage in MB")

    # Performance characteristics
    avg_inference_time_ms: Optional[float] = Field(default=None, ge=0, description="Avg inference time")
    throughput_texts_per_sec: Optional[float] = Field(default=None, ge=0, description="Throughput")

    # Model metadata
    model_size_mb: Optional[float] = Field(default=None, ge=0, description="Model size on disk")
    num_parameters: Optional[int] = Field(default=None, ge=1, description="Number of parameters")
    architecture: Optional[str] = Field(default=None, description="Model architecture")

    # Loading info
    loaded_at: datetime = Field(default_factory=datetime.now, description="Load timestamp")
    load_time_seconds: Optional[float] = Field(default=None, ge=0, description="Load time")

    class Config:
        use_enum_values = True
        validate_assignment = True


class LocalEmbeddingRequest(BaseModel):
    """Request for local embedding generation"""
    texts: List[str] = Field(..., min_items=1, description="Texts to embed")

    # Processing options
    batch_size: Optional[int] = Field(default=None, ge=1, description="Override batch size")
    normalize: Optional[bool] = Field(default=None, description="Override normalization")
    convert_to_tensor: bool = Field(default=False, description="Return as tensor")
    show_progress: bool = Field(default=False, description="Show progress bar")

    # Preprocessing
    truncate: bool = Field(default=True, description="Truncate long sequences")
    padding: bool = Field(default=True, description="Pad sequences to same length")
    add_special_tokens: bool = Field(default=True, description="Add special tokens")

    # Advanced options
    return_attention_mask: bool = Field(default=False, description="Return attention masks")
    return_token_embeddings: bool = Field(default=False, description="Return token-level embeddings")

    @validator("texts")
    def validate_texts(cls, v):
        """Validate texts are not empty"""
        if any(not text.strip() for text in v):
            raise ValueError("All texts must be non-empty")
        return v

    class Config:
        validate_assignment = True


class LocalEmbeddingResult(BaseModel):
    """Result from local embedding generation"""
    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    dimension: int = Field(..., ge=1, description="Embedding dimension")

    # Model information
    model: str = Field(..., description="Model used")
    framework: LocalModelFramework = Field(..., description="Framework used")
    device: str = Field(..., description="Device used")

    # Processing information
    num_texts: int = Field(..., ge=1, description="Number of texts processed")
    truncated_texts: List[int] = Field(default_factory=list, description="Indices of truncated texts")
    avg_tokens_per_text: float = Field(..., ge=0, description="Average tokens per text")

    # Performance metrics
    inference_time_ms: float = Field(..., ge=0, description="Total inference time")
    preprocessing_time_ms: float = Field(..., ge=0, description="Preprocessing time")
    postprocessing_time_ms: float = Field(..., ge=0, description="Postprocessing time")
    total_time_ms: float = Field(..., ge=0, description="Total processing time")

    # Memory usage
    peak_memory_mb: Optional[float] = Field(default=None, ge=0, description="Peak memory usage")
    gpu_memory_mb: Optional[float] = Field(default=None, ge=0, description="GPU memory usage")

    # Optional outputs
    attention_masks: Optional[List[List[int]]] = Field(default=None, description="Attention masks")
    token_embeddings: Optional[List[Any]] = Field(default=None, description="Token-level embeddings")

    @validator("dimension", always=True)
    def calculate_dimension(cls, v, values):
        """Calculate dimension from embeddings"""
        if "embeddings" in values and values["embeddings"] and values["embeddings"][0]:
            return len(values["embeddings"][0])
        return v

    @validator("total_time_ms", always=True)
    def calculate_total_time(cls, v, values):
        """Calculate total time from components"""
        components = ["inference_time_ms", "preprocessing_time_ms", "postprocessing_time_ms"]
        times = [values.get(c, 0) for c in components if c in values]
        if times:
            return sum(times)
        return v or 0

    class Config:
        use_enum_values = True
        validate_assignment = True


class LocalModelCache(BaseModel):
    """Cache configuration for local models"""
    enabled: bool = Field(default=True, description="Enable model caching")
    cache_dir: str = Field(default="~/.cache/embeddings", description="Cache directory")

    # Cache settings
    max_models: int = Field(default=3, ge=1, description="Max models to keep in memory")
    max_size_gb: float = Field(default=10, ge=0.1, description="Max total cache size in GB")
    ttl_hours: int = Field(default=24, ge=1, description="Time to live in hours")

    # Model management
    preload_models: List[str] = Field(default_factory=list, description="Models to preload")
    pin_models: List[str] = Field(default_factory=list, description="Models to pin in cache")

    # Cache statistics
    cached_models: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Currently cached models"
    )
    total_size_mb: float = Field(default=0, ge=0, description="Total cache size in MB")
    hit_count: int = Field(default=0, ge=0, description="Cache hits")
    miss_count: int = Field(default=0, ge=0, description="Cache misses")

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hit_count + self.miss_count
        if total > 0:
            return self.hit_count / total
        return 0.0

    class Config:
        validate_assignment = True


class LocalBenchmarkResult(BaseModel):
    """Benchmark results for local embedding model"""
    model: str = Field(..., description="Model name")
    framework: LocalModelFramework = Field(..., description="Framework used")
    device: str = Field(..., description="Device used")

    # Test parameters
    num_texts: int = Field(..., ge=1, description="Number of test texts")
    avg_text_length: int = Field(..., ge=1, description="Average text length")
    batch_size: int = Field(..., ge=1, description="Batch size used")

    # Performance metrics
    total_time_seconds: float = Field(..., ge=0, description="Total benchmark time")
    texts_per_second: float = Field(..., ge=0, description="Throughput")
    avg_latency_ms: float = Field(..., ge=0, description="Average latency per text")
    p50_latency_ms: float = Field(..., ge=0, description="50th percentile latency")
    p95_latency_ms: float = Field(..., ge=0, description="95th percentile latency")
    p99_latency_ms: float = Field(..., ge=0, description="99th percentile latency")

    # Resource usage
    avg_cpu_percent: float = Field(..., ge=0, le=100, description="Average CPU usage")
    peak_memory_mb: float = Field(..., ge=0, description="Peak memory usage")
    avg_gpu_percent: Optional[float] = Field(default=None, ge=0, le=100, description="Average GPU usage")
    peak_gpu_memory_mb: Optional[float] = Field(default=None, ge=0, description="Peak GPU memory")

    # Quality metrics (if reference embeddings provided)
    avg_cosine_similarity: Optional[float] = Field(
        default=None,
        ge=-1,
        le=1,
        description="Avg similarity to reference"
    )
    min_cosine_similarity: Optional[float] = Field(
        default=None,
        ge=-1,
        le=1,
        description="Min similarity to reference"
    )

    # Timestamp
    benchmark_date: datetime = Field(default_factory=datetime.now, description="Benchmark timestamp")

    @validator("texts_per_second", always=True)
    def calculate_throughput(cls, v, values):
        """Calculate throughput from total time and num texts"""
        if "total_time_seconds" in values and "num_texts" in values:
            if values["total_time_seconds"] > 0:
                return values["num_texts"] / values["total_time_seconds"]
        return v or 0

    class Config:
        use_enum_values = True
        validate_assignment = True