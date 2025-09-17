"""
Hybrid search schemas combining multiple retrieval methods
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum

from schemas.retrieval.search import SearchType, SearchResult, SearchFilter


class HybridSearchMethod(str, Enum):
    """Methods for hybrid search"""
    VECTOR_KEYWORD = "vector_keyword"
    VECTOR_SEMANTIC = "vector_semantic"
    MULTI_VECTOR = "multi_vector"
    ENSEMBLE = "ensemble"
    CASCADED = "cascaded"


class FusionMethod(str, Enum):
    """Methods for fusing results from different searches"""
    RRF = "rrf"  # Reciprocal Rank Fusion
    LINEAR = "linear"  # Linear combination
    WEIGHTED = "weighted"  # Weighted combination
    DISJUNCTIVE = "disjunctive"  # Union of results
    CONJUNCTIVE = "conjunctive"  # Intersection of results


class HybridSearchConfig(BaseModel):
    """Configuration for hybrid search"""
    method: HybridSearchMethod = Field(
        default=HybridSearchMethod.VECTOR_KEYWORD,
        description="Hybrid search method"
    )
    fusion_method: FusionMethod = Field(default=FusionMethod.RRF, description="Result fusion method")

    # Component weights
    vector_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Weight for vector search")
    keyword_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Weight for keyword search")
    semantic_weight: float = Field(default=0.0, ge=0.0, le=1.0, description="Weight for semantic search")

    # Search parameters
    vector_top_k: int = Field(default=50, ge=1, description="Top K for vector search")
    keyword_top_k: int = Field(default=50, ge=1, description="Top K for keyword search")
    final_top_k: int = Field(default=10, ge=1, description="Final number of results")

    # Advanced settings
    normalize_scores: bool = Field(default=True, description="Normalize scores before fusion")
    remove_duplicates: bool = Field(default=True, description="Remove duplicate results")
    min_score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum score threshold")

    # RRF parameters
    rrf_k: int = Field(default=60, ge=1, description="K parameter for RRF")

    @validator("keyword_weight")
    def validate_weights(cls, v, values):
        """Validate weights sum to 1.0 for weighted methods"""
        if "fusion_method" in values and values["fusion_method"] in [FusionMethod.LINEAR, FusionMethod.WEIGHTED]:
            vector_w = values.get("vector_weight", 0.7)
            semantic_w = values.get("semantic_weight", 0.0)
            total = vector_w + v + semantic_w
            if abs(total - 1.0) > 0.001:
                raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class HybridSearchQuery(BaseModel):
    """Query for hybrid search"""
    query: str = Field(..., min_length=1, description="Search query text")

    # Search components to use
    use_vector: bool = Field(default=True, description="Use vector search")
    use_keyword: bool = Field(default=True, description="Use keyword search")
    use_semantic: bool = Field(default=False, description="Use semantic search")

    # Component-specific parameters
    vector_embedding: Optional[List[float]] = Field(default=None, description="Pre-computed embedding")
    keyword_fields: Optional[List[str]] = Field(default=None, description="Fields for keyword search")
    semantic_context: Optional[str] = Field(default=None, description="Context for semantic search")

    # Filters
    filters: List[SearchFilter] = Field(default_factory=list, description="Search filters")
    date_range: Optional[Dict[str, datetime]] = Field(default=None, description="Date range filter")

    # Result options
    include_explanations: bool = Field(default=False, description="Include score explanations")
    include_metadata: bool = Field(default=True, description="Include result metadata")
    highlight_matches: bool = Field(default=False, description="Highlight matching terms")

    # Collections/indices
    collections: Optional[List[str]] = Field(default=None, description="Target collections")

    class Config:
        validate_assignment = True


class HybridSearchResult(BaseModel):
    """Individual result from hybrid search"""
    id: str = Field(..., description="Result ID")
    content: str = Field(..., description="Text content")
    final_score: float = Field(..., ge=0.0, le=1.0, description="Combined relevance score")

    # Component scores
    vector_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Vector search score")
    keyword_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Keyword search score")
    semantic_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Semantic search score")

    # Source information
    source_methods: List[SearchType] = Field(..., description="Methods that returned this result")
    primary_source: SearchType = Field(..., description="Primary source method")

    # Metadata
    document_id: Optional[str] = Field(default=None, description="Source document ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")
    highlights: Optional[Dict[str, List[str]]] = Field(default=None, description="Highlighted snippets")

    # Ranking information
    vector_rank: Optional[int] = Field(default=None, description="Rank in vector search")
    keyword_rank: Optional[int] = Field(default=None, description="Rank in keyword search")
    final_rank: int = Field(..., ge=1, description="Final rank in hybrid results")

    # Explanation
    score_explanation: Optional[Dict[str, Any]] = Field(default=None, description="Score calculation details")

    class Config:
        validate_assignment = True


class HybridSearchResponse(BaseModel):
    """Response from hybrid search"""
    query: str = Field(..., description="Original query")
    results: List[HybridSearchResult] = Field(..., description="Hybrid search results")
    total_results: int = Field(..., ge=0, description="Total matching results")

    # Search metadata
    method: HybridSearchMethod = Field(..., description="Hybrid method used")
    fusion_method: FusionMethod = Field(..., description="Fusion method used")

    # Component statistics
    vector_results_count: int = Field(default=0, ge=0, description="Vector search results")
    keyword_results_count: int = Field(default=0, ge=0, description="Keyword search results")
    overlap_count: int = Field(default=0, ge=0, description="Results found by multiple methods")

    # Performance metrics
    total_search_time_ms: float = Field(..., ge=0, description="Total search time")
    vector_search_time_ms: Optional[float] = Field(default=None, ge=0, description="Vector search time")
    keyword_search_time_ms: Optional[float] = Field(default=None, ge=0, description="Keyword search time")
    fusion_time_ms: Optional[float] = Field(default=None, ge=0, description="Result fusion time")

    # Quality metrics
    avg_final_score: float = Field(..., ge=0.0, le=1.0, description="Average final score")
    score_distribution: Optional[Dict[str, float]] = Field(default=None, description="Score distribution")

    @validator("avg_final_score", always=True)
    def calculate_avg_score(cls, v, values):
        """Calculate average final score"""
        if "results" in values and values["results"]:
            scores = [r.final_score for r in values["results"]]
            return sum(scores) / len(scores)
        return v or 0.0

    @validator("overlap_count", always=True)
    def calculate_overlap(cls, v, values):
        """Calculate overlap between search methods"""
        if "results" in values:
            overlap = sum(1 for r in values["results"] if len(r.source_methods) > 1)
            return overlap
        return v or 0

    class Config:
        use_enum_values = True
        validate_assignment = True


class MultiStageSearch(BaseModel):
    """Configuration for multi-stage hybrid search"""
    stages: List[Dict[str, Any]] = Field(..., min_items=1, description="Search stages configuration")

    # Stage execution
    execution_mode: Literal["sequential", "parallel", "adaptive"] = Field(
        default="sequential",
        description="How to execute stages"
    )
    early_termination: bool = Field(default=False, description="Stop if enough results found")
    termination_threshold: int = Field(default=10, ge=1, description="Results needed for termination")

    # Stage transition
    pass_results_between_stages: bool = Field(default=True, description="Pass results between stages")
    aggregate_results: bool = Field(default=True, description="Aggregate results from all stages")

    # Performance
    stage_timeout_ms: float = Field(default=5000, ge=100, description="Timeout per stage")
    total_timeout_ms: Optional[float] = Field(default=None, description="Total timeout for all stages")

    @validator("stages")
    def validate_stages(cls, v):
        """Validate stage configuration"""
        for i, stage in enumerate(v):
            if "type" not in stage:
                raise ValueError(f"Stage {i} missing 'type' field")
            if "config" not in stage:
                raise ValueError(f"Stage {i} missing 'config' field")
        return v

    class Config:
        validate_assignment = True


class HybridSearchOptimization(BaseModel):
    """Optimization parameters for hybrid search"""
    # Weight optimization
    optimize_weights: bool = Field(default=False, description="Automatically optimize weights")
    optimization_method: Literal["grid_search", "bayesian", "evolutionary"] = Field(
        default="grid_search",
        description="Weight optimization method"
    )

    # Training data
    training_queries: Optional[List[str]] = Field(default=None, description="Queries for optimization")
    relevance_judgments: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Relevance judgments"
    )

    # Optimization constraints
    min_vector_weight: float = Field(default=0.1, ge=0.0, le=1.0, description="Min vector weight")
    max_vector_weight: float = Field(default=0.9, ge=0.0, le=1.0, description="Max vector weight")
    weight_step: float = Field(default=0.1, ge=0.01, le=0.5, description="Step size for grid search")

    # Performance targets
    target_metric: Literal["ndcg", "map", "mrr", "precision"] = Field(
        default="ndcg",
        description="Metric to optimize"
    )
    target_value: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Target metric value")

    @validator("max_vector_weight")
    def validate_weight_range(cls, v, values):
        """Validate weight range is valid"""
        if "min_vector_weight" in values and v < values["min_vector_weight"]:
            raise ValueError("max_vector_weight must be >= min_vector_weight")
        return v

    class Config:
        validate_assignment = True


class HybridSearchMetrics(BaseModel):
    """Metrics for hybrid search performance"""
    # Usage metrics
    total_searches: int = Field(..., ge=0, description="Total hybrid searches")
    avg_results_per_search: float = Field(..., ge=0, description="Average results per search")

    # Component usage
    vector_only_searches: int = Field(default=0, ge=0, description="Vector-only searches")
    keyword_only_searches: int = Field(default=0, ge=0, description="Keyword-only searches")
    full_hybrid_searches: int = Field(default=0, ge=0, description="Full hybrid searches")

    # Performance metrics
    avg_total_time_ms: float = Field(..., ge=0, description="Average total search time")
    avg_vector_time_ms: float = Field(..., ge=0, description="Average vector search time")
    avg_keyword_time_ms: float = Field(..., ge=0, description="Average keyword search time")
    avg_fusion_time_ms: float = Field(..., ge=0, description="Average fusion time")

    # Quality metrics
    avg_overlap_rate: float = Field(..., ge=0.0, le=1.0, description="Average result overlap rate")
    avg_score_improvement: float = Field(..., description="Average score improvement from fusion")

    # Fusion method effectiveness
    fusion_method_usage: Dict[str, int] = Field(..., description="Usage count by fusion method")
    fusion_method_performance: Dict[str, float] = Field(..., description="Avg score by fusion method")

    # Weight distribution
    avg_vector_weight: float = Field(..., ge=0.0, le=1.0, description="Average vector weight used")
    avg_keyword_weight: float = Field(..., ge=0.0, le=1.0, description="Average keyword weight used")

    # Time period
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")

    class Config:
        validate_assignment = True


class HybridSearchExperiment(BaseModel):
    """Configuration for A/B testing hybrid search"""
    experiment_id: str = Field(..., description="Unique experiment ID")
    name: str = Field(..., description="Experiment name")

    # Variants
    control_config: HybridSearchConfig = Field(..., description="Control configuration")
    variant_configs: List[HybridSearchConfig] = Field(..., min_items=1, description="Variant configurations")

    # Traffic allocation
    traffic_percentages: List[float] = Field(..., description="Traffic % for each variant")
    min_sample_size: int = Field(default=100, ge=10, description="Minimum sample size per variant")

    # Metrics to track
    tracked_metrics: List[str] = Field(
        default_factory=lambda: ["click_through_rate", "avg_score", "search_time"],
        description="Metrics to track"
    )

    # Experiment settings
    start_date: datetime = Field(..., description="Experiment start date")
    end_date: Optional[datetime] = Field(default=None, description="Experiment end date")
    auto_conclude: bool = Field(default=False, description="Auto-conclude when significant")
    significance_level: float = Field(default=0.05, ge=0.01, le=0.1, description="Statistical significance level")

    @validator("traffic_percentages")
    def validate_traffic(cls, v, values):
        """Validate traffic allocation"""
        if "variant_configs" in values:
            expected_length = len(values["variant_configs"]) + 1  # +1 for control
            if len(v) != expected_length:
                raise ValueError(f"Need {expected_length} traffic percentages")
            if abs(sum(v) - 1.0) > 0.001:
                raise ValueError("Traffic percentages must sum to 1.0")
        return v

    class Config:
        validate_assignment = True