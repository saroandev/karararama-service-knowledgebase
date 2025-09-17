"""
Search and retrieval schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class SearchType(str, Enum):
    """Types of search operations"""
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    SEMANTIC = "semantic"
    FUZZY = "fuzzy"


class SearchStrategy(str, Enum):
    """Search strategies for retrieval"""
    SIMILARITY = "similarity"  # Pure vector similarity
    MMR = "mmr"  # Maximal Marginal Relevance
    DIVERSITY = "diversity"  # Diverse results
    WEIGHTED = "weighted"  # Weighted combination


class SearchQuery(BaseModel):
    """Search query request"""
    query: str = Field(..., min_length=1, description="Search query text")
    search_type: SearchType = Field(default=SearchType.VECTOR, description="Type of search")

    # Search parameters
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum score threshold")

    # Vector search parameters
    embedding: Optional[List[float]] = Field(default=None, description="Pre-computed query embedding")
    collection: Optional[str] = Field(default=None, description="Target collection/index")

    # Filters
    filters: Dict[str, Any] = Field(default_factory=dict, description="Metadata filters")
    date_from: Optional[datetime] = Field(default=None, description="Start date filter")
    date_to: Optional[datetime] = Field(default=None, description="End date filter")
    document_ids: Optional[List[str]] = Field(default=None, description="Filter by document IDs")

    # Advanced options
    include_metadata: bool = Field(default=True, description="Include metadata in results")
    include_embeddings: bool = Field(default=False, description="Include embeddings in results")
    include_scores: bool = Field(default=True, description="Include similarity scores")

    # Strategy
    strategy: SearchStrategy = Field(default=SearchStrategy.SIMILARITY, description="Search strategy")
    diversity_lambda: float = Field(default=0.5, ge=0.0, le=1.0, description="Diversity parameter for MMR")

    @validator("embedding")
    def validate_embedding(cls, v, values):
        """Validate embedding if provided"""
        if v and "search_type" in values and values["search_type"] == SearchType.KEYWORD:
            raise ValueError("Embedding not needed for keyword search")
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class SearchFilter(BaseModel):
    """Advanced search filters"""
    field: str = Field(..., description="Field to filter on")
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "regex"] = Field(
        ..., description="Filter operator"
    )
    value: Any = Field(..., description="Filter value")

    # Optional parameters
    case_sensitive: bool = Field(default=False, description="Case sensitive matching")
    fuzzy_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Fuzzy match threshold")

    class Config:
        validate_assignment = True


class SearchResult(BaseModel):
    """Individual search result"""
    id: str = Field(..., description="Result ID")
    content: str = Field(..., description="Text content")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")

    # Metadata
    document_id: Optional[str] = Field(default=None, description="Source document ID")
    chunk_index: Optional[int] = Field(default=None, description="Chunk index in document")
    page_number: Optional[int] = Field(default=None, description="Page number in document")

    # Additional data
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")
    embedding: Optional[List[float]] = Field(default=None, description="Result embedding vector")
    highlights: Optional[List[str]] = Field(default=None, description="Highlighted snippets")

    # Source information
    source_type: Optional[str] = Field(default=None, description="Source type (pdf, web, etc.)")
    source_url: Optional[str] = Field(default=None, description="Source URL if available")
    source_title: Optional[str] = Field(default=None, description="Source document title")

    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    class Config:
        validate_assignment = True


class SearchResponse(BaseModel):
    """Search operation response"""
    query: str = Field(..., description="Original query")
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., ge=0, description="Total matching results")

    # Search metadata
    search_type: SearchType = Field(..., description="Search type used")
    search_time_ms: float = Field(..., ge=0, description="Search execution time")

    # Aggregations
    facets: Optional[Dict[str, List[Dict[str, Any]]]] = Field(default=None, description="Faceted results")
    stats: Optional[Dict[str, Any]] = Field(default=None, description="Result statistics")

    # Query understanding
    processed_query: Optional[str] = Field(default=None, description="Processed/expanded query")
    query_embedding: Optional[List[float]] = Field(default=None, description="Query embedding")
    detected_intent: Optional[str] = Field(default=None, description="Detected query intent")

    # Pagination
    offset: int = Field(default=0, ge=0, description="Result offset")
    limit: int = Field(..., ge=1, description="Result limit")
    has_more: bool = Field(default=False, description="More results available")

    @validator("has_more", always=True)
    def calculate_has_more(cls, v, values):
        """Calculate if more results are available"""
        if "total_results" in values and "offset" in values and "limit" in values:
            return values["total_results"] > values["offset"] + values["limit"]
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class BulkSearchRequest(BaseModel):
    """Bulk search request for multiple queries"""
    queries: List[SearchQuery] = Field(..., min_items=1, description="Search queries")

    # Bulk options
    parallel: bool = Field(default=True, description="Process queries in parallel")
    batch_size: int = Field(default=10, ge=1, description="Batch size for processing")
    timeout_seconds: Optional[float] = Field(default=None, description="Total timeout")

    # Result options
    merge_results: bool = Field(default=False, description="Merge results from all queries")
    deduplicate: bool = Field(default=True, description="Remove duplicate results")

    class Config:
        validate_assignment = True


class SearchAggregation(BaseModel):
    """Search result aggregations"""
    field: str = Field(..., description="Field to aggregate on")
    type: Literal["terms", "stats", "date_histogram", "range"] = Field(..., description="Aggregation type")

    # Type-specific parameters
    size: Optional[int] = Field(default=10, ge=1, description="Number of buckets (for terms)")
    interval: Optional[str] = Field(default=None, description="Date histogram interval")
    ranges: Optional[List[Dict[str, Any]]] = Field(default=None, description="Range boundaries")

    # Results
    buckets: Optional[List[Dict[str, Any]]] = Field(default=None, description="Aggregation buckets")
    stats: Optional[Dict[str, float]] = Field(default=None, description="Statistical aggregations")

    class Config:
        validate_assignment = True


class SearchContext(BaseModel):
    """Context for search operations"""
    user_id: Optional[str] = Field(default=None, description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Session identifier")

    # Personalization
    user_preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    search_history: List[str] = Field(default_factory=list, description="Recent searches")

    # Context information
    location: Optional[str] = Field(default=None, description="User location")
    language: str = Field(default="en", description="Preferred language")
    timezone: Optional[str] = Field(default=None, description="User timezone")

    # Access control
    allowed_collections: Optional[List[str]] = Field(default=None, description="Allowed collections")
    excluded_sources: Optional[List[str]] = Field(default=None, description="Excluded sources")

    class Config:
        validate_assignment = True


class SearchMetrics(BaseModel):
    """Metrics for search operations"""
    total_searches: int = Field(..., ge=0, description="Total searches performed")
    avg_response_time_ms: float = Field(..., ge=0, description="Average response time")
    avg_results_per_query: float = Field(..., ge=0, description="Average results per query")

    # Quality metrics
    avg_top_score: float = Field(..., ge=0.0, le=1.0, description="Average top result score")
    zero_result_rate: float = Field(..., ge=0.0, le=1.0, description="Rate of zero result queries")
    click_through_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="CTR if tracked")

    # Performance breakdown
    vector_search_time_ms: Optional[float] = Field(default=None, ge=0, description="Vector search time")
    filter_time_ms: Optional[float] = Field(default=None, ge=0, description="Filter application time")
    ranking_time_ms: Optional[float] = Field(default=None, ge=0, description="Ranking/scoring time")

    # Cache metrics
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Cache hit rate")
    cached_queries: int = Field(default=0, ge=0, description="Number of cached queries")

    # Time period
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")

    class Config:
        validate_assignment = True


class SearchExplanation(BaseModel):
    """Explanation for search result ranking"""
    result_id: str = Field(..., description="Result ID")
    total_score: float = Field(..., description="Total relevance score")

    # Score breakdown
    vector_score: Optional[float] = Field(default=None, description="Vector similarity score")
    keyword_score: Optional[float] = Field(default=None, description="Keyword match score")
    boost_score: Optional[float] = Field(default=None, description="Boost/penalty score")

    # Factors
    matching_terms: List[str] = Field(default_factory=list, description="Matching query terms")
    field_matches: Dict[str, float] = Field(default_factory=dict, description="Field-level scores")

    # Explanation
    explanation: str = Field(..., description="Human-readable explanation")
    debug_info: Optional[Dict[str, Any]] = Field(default=None, description="Debug information")

    class Config:
        validate_assignment = True