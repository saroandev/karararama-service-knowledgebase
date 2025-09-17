"""
Reranker schemas for result optimization
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class RerankerType(str, Enum):
    """Types of reranking models"""
    CROSS_ENCODER = "cross_encoder"
    COLBERT = "colbert"
    COHERE = "cohere"
    OPENAI = "openai"
    LOCAL = "local"
    RULE_BASED = "rule_based"


class RerankerModel(str, Enum):
    """Common reranker models"""
    # Cross-encoder models
    MS_MARCO_MINILM = "ms-marco-MiniLM-L-6-v2"
    MS_MARCO_ELECTRA = "ms-marco-electra-base"
    BGE_RERANKER_BASE = "BAAI/bge-reranker-base"
    BGE_RERANKER_LARGE = "BAAI/bge-reranker-large"

    # Cohere models
    COHERE_RERANK_ENGLISH = "rerank-english-v2.0"
    COHERE_RERANK_MULTILINGUAL = "rerank-multilingual-v2.0"


class RerankerConfig(BaseModel):
    """Configuration for reranking"""
    type: RerankerType = Field(..., description="Reranker type")
    model: Optional[str] = Field(default=None, description="Model name or path")

    # Model parameters
    batch_size: int = Field(default=32, ge=1, description="Batch size for processing")
    max_length: int = Field(default=512, ge=1, description="Maximum input length")
    device: str = Field(default="cpu", description="Device to use (cpu/cuda/mps)")

    # API settings (if applicable)
    api_key: Optional[str] = Field(default=None, description="API key for external services")
    api_base_url: Optional[str] = Field(default=None, description="API base URL")
    timeout_seconds: int = Field(default=30, ge=1, description="API timeout")

    # Reranking parameters
    top_n: Optional[int] = Field(default=None, ge=1, description="Return top N results")
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Min score threshold")
    normalize_scores: bool = Field(default=True, description="Normalize output scores")

    # Performance settings
    use_cache: bool = Field(default=True, description="Cache reranking results")
    parallel_workers: int = Field(default=1, ge=1, description="Number of parallel workers")

    @validator("model")
    def validate_model(cls, v, values):
        """Validate model based on type"""
        if "type" in values:
            reranker_type = values["type"]
            if reranker_type in [RerankerType.CROSS_ENCODER, RerankerType.COLBERT] and not v:
                raise ValueError(f"{reranker_type} requires a model to be specified")
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class RerankerRequest(BaseModel):
    """Request for reranking results"""
    query: str = Field(..., min_length=1, description="Query text")
    documents: List[str] = Field(..., min_items=1, description="Documents to rerank")

    # Optional document metadata
    document_ids: Optional[List[str]] = Field(default=None, description="Document IDs")
    initial_scores: Optional[List[float]] = Field(default=None, description="Initial relevance scores")

    # Reranking options
    top_k: Optional[int] = Field(default=None, ge=1, description="Number of results to return")
    return_documents: bool = Field(default=True, description="Return document text")
    return_scores: bool = Field(default=True, description="Return relevance scores")

    # Advanced options
    boost_recent: bool = Field(default=False, description="Boost recent documents")
    diversity_factor: float = Field(default=0.0, ge=0.0, le=1.0, description="Result diversity factor")

    @validator("document_ids")
    def validate_document_ids(cls, v, values):
        """Ensure document_ids matches documents length"""
        if v and "documents" in values and len(v) != len(values["documents"]):
            raise ValueError("document_ids must match documents length")
        return v

    @validator("initial_scores")
    def validate_initial_scores(cls, v, values):
        """Ensure initial_scores matches documents length"""
        if v and "documents" in values and len(v) != len(values["documents"]):
            raise ValueError("initial_scores must match documents length")
        return v

    class Config:
        validate_assignment = True


class RerankedResult(BaseModel):
    """Individual reranked result"""
    index: int = Field(..., ge=0, description="Original index in input documents")
    document: Optional[str] = Field(default=None, description="Document text")
    score: float = Field(..., description="Reranking score")

    # Metadata
    document_id: Optional[str] = Field(default=None, description="Document ID if provided")
    initial_score: Optional[float] = Field(default=None, description="Initial score before reranking")
    score_change: Optional[float] = Field(default=None, description="Change in score")

    # Explanation
    relevance_explanation: Optional[str] = Field(default=None, description="Why this result is relevant")
    boost_factors: Optional[Dict[str, float]] = Field(default=None, description="Applied boost factors")

    @validator("score_change", always=True)
    def calculate_score_change(cls, v, values):
        """Calculate score change if initial score is provided"""
        if "initial_score" in values and values["initial_score"] is not None and "score" in values:
            return values["score"] - values["initial_score"]
        return v

    class Config:
        validate_assignment = True


class RerankerResponse(BaseModel):
    """Response from reranking operation"""
    query: str = Field(..., description="Original query")
    results: List[RerankedResult] = Field(..., description="Reranked results")

    # Metadata
    model: str = Field(..., description="Model used for reranking")
    reranking_time_ms: float = Field(..., ge=0, description="Reranking time in milliseconds")

    # Statistics
    total_documents: int = Field(..., ge=1, description="Total documents processed")
    returned_documents: int = Field(..., ge=0, description="Number of documents returned")
    avg_score_change: Optional[float] = Field(default=None, description="Average score change")

    # Quality metrics
    score_distribution: Optional[Dict[str, float]] = Field(
        default=None,
        description="Score distribution stats"
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in reranking"
    )

    @validator("returned_documents", always=True)
    def calculate_returned_documents(cls, v, values):
        """Calculate number of returned documents"""
        if "results" in values:
            return len(values["results"])
        return v or 0

    @validator("avg_score_change", always=True)
    def calculate_avg_score_change(cls, v, values):
        """Calculate average score change"""
        if "results" in values:
            changes = [r.score_change for r in values["results"] if r.score_change is not None]
            if changes:
                return sum(changes) / len(changes)
        return v

    class Config:
        validate_assignment = True


class BatchRerankerRequest(BaseModel):
    """Request for batch reranking multiple queries"""
    queries: List[str] = Field(..., min_items=1, description="Query texts")
    document_sets: List[List[str]] = Field(..., min_items=1, description="Document sets for each query")

    # Batch options
    parallel_processing: bool = Field(default=True, description="Process in parallel")
    batch_size: int = Field(default=10, ge=1, description="Batch size")

    # Common options for all queries
    top_k: Optional[int] = Field(default=None, ge=1, description="Top K for all queries")
    return_documents: bool = Field(default=True, description="Return documents")

    @validator("document_sets")
    def validate_document_sets(cls, v, values):
        """Ensure document_sets matches queries length"""
        if "queries" in values and len(v) != len(values["queries"]):
            raise ValueError("document_sets must match queries length")
        return v

    class Config:
        validate_assignment = True


class RerankerComparison(BaseModel):
    """Comparison of different reranker models"""
    query: str = Field(..., description="Query used for comparison")
    documents: List[str] = Field(..., description="Documents reranked")

    # Results from different models
    model_results: Dict[str, List[RerankedResult]] = Field(
        ...,
        description="Results from each model"
    )

    # Performance comparison
    model_times: Dict[str, float] = Field(..., description="Processing time for each model")
    model_scores: Dict[str, List[float]] = Field(..., description="Scores from each model")

    # Agreement metrics
    kendall_tau: Optional[Dict[str, float]] = Field(
        default=None,
        description="Kendall's tau between models"
    )
    spearman_correlation: Optional[Dict[str, float]] = Field(
        default=None,
        description="Spearman correlation between models"
    )

    # Best model selection
    recommended_model: Optional[str] = Field(default=None, description="Recommended model")
    recommendation_reason: Optional[str] = Field(default=None, description="Reason for recommendation")

    class Config:
        validate_assignment = True


class RerankerMetrics(BaseModel):
    """Metrics for reranker performance"""
    model: str = Field(..., description="Reranker model")

    # Usage metrics
    total_queries: int = Field(..., ge=0, description="Total queries processed")
    total_documents: int = Field(..., ge=0, description="Total documents reranked")
    avg_documents_per_query: float = Field(..., ge=0, description="Average documents per query")

    # Performance metrics
    avg_reranking_time_ms: float = Field(..., ge=0, description="Average reranking time")
    p50_time_ms: float = Field(..., ge=0, description="Median reranking time")
    p95_time_ms: float = Field(..., ge=0, description="95th percentile time")
    p99_time_ms: float = Field(..., ge=0, description="99th percentile time")

    # Quality metrics
    avg_score_improvement: float = Field(..., description="Average score improvement")
    reordering_rate: float = Field(..., ge=0.0, le=1.0, description="Rate of result reordering")

    # Cache metrics
    cache_hits: int = Field(default=0, ge=0, description="Number of cache hits")
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Cache hit rate")

    # Resource usage
    avg_memory_mb: float = Field(..., ge=0, description="Average memory usage")
    peak_memory_mb: float = Field(..., ge=0, description="Peak memory usage")

    # Time period
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")

    @validator("avg_documents_per_query", always=True)
    def calculate_avg_documents(cls, v, values):
        """Calculate average documents per query"""
        if "total_queries" in values and values["total_queries"] > 0 and "total_documents" in values:
            return values["total_documents"] / values["total_queries"]
        return v or 0

    class Config:
        validate_assignment = True


class RerankingStrategy(BaseModel):
    """Strategy for combining multiple rerankers"""
    primary_reranker: RerankerConfig = Field(..., description="Primary reranker configuration")
    fallback_rerankers: List[RerankerConfig] = Field(
        default_factory=list,
        description="Fallback rerankers"
    )

    # Combination strategy
    combination_method: Literal["cascade", "ensemble", "voting", "weighted"] = Field(
        default="cascade",
        description="How to combine rerankers"
    )
    weights: Optional[List[float]] = Field(default=None, description="Weights for ensemble")

    # Performance settings
    timeout_per_reranker: float = Field(default=5.0, ge=0.1, description="Timeout per reranker")
    fail_fast: bool = Field(default=False, description="Fail on first error")

    @validator("weights")
    def validate_weights(cls, v, values):
        """Validate weights for ensemble method"""
        if v and "combination_method" in values and values["combination_method"] == "weighted":
            total_rerankers = 1 + len(values.get("fallback_rerankers", []))
            if len(v) != total_rerankers:
                raise ValueError("Number of weights must match total rerankers")
            if abs(sum(v) - 1.0) > 0.001:
                raise ValueError("Weights must sum to 1.0")
        return v

    class Config:
        validate_assignment = True