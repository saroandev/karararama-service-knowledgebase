"""
Query pipeline schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum

from schemas.retrieval.search import SearchQuery, SearchResult, SearchStrategy
from schemas.retrieval.reranker import RerankerConfig, RerankedResult
from schemas.generation.llm import GenerationRequest, GenerationResponse


class QueryStage(str, Enum):
    """Stages in the query pipeline"""
    PARSE = "parse"
    EMBED = "embed"
    RETRIEVE = "retrieve"
    RERANK = "rerank"
    GENERATE = "generate"
    POST_PROCESS = "post_process"
    VALIDATE = "validate"


class QueryMode(str, Enum):
    """Query processing modes"""
    SIMPLE = "simple"  # Basic retrieval + generation
    HYBRID = "hybrid"  # Hybrid search with reranking
    MULTI_HOP = "multi_hop"  # Multi-step reasoning
    CONVERSATIONAL = "conversational"  # With chat history
    STREAMING = "streaming"  # Streaming response


class QueryPipelineConfig(BaseModel):
    """Configuration for query pipeline"""
    # Pipeline settings
    pipeline_name: str = Field(default="default_query", description="Pipeline name")
    mode: QueryMode = Field(default=QueryMode.SIMPLE, description="Query mode")

    # Retrieval settings
    retrieval_enabled: bool = Field(default=True, description="Enable retrieval")
    search_strategy: SearchStrategy = Field(default=SearchStrategy.SIMILARITY, description="Search strategy")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to retrieve")

    # Reranking settings
    reranking_enabled: bool = Field(default=False, description="Enable reranking")
    reranker_config: Optional[RerankerConfig] = Field(default=None, description="Reranker configuration")
    rerank_top_k: int = Field(default=5, ge=1, le=50, description="Top K after reranking")

    # Generation settings
    generation_enabled: bool = Field(default=True, description="Enable answer generation")
    generation_model: str = Field(default="gpt-4o-mini", description="Generation model")
    max_tokens: int = Field(default=1000, ge=1, description="Max generation tokens")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Generation temperature")

    # Advanced options
    use_chat_history: bool = Field(default=False, description="Use chat history for context")
    include_sources: bool = Field(default=True, description="Include source citations")
    include_confidence: bool = Field(default=False, description="Include confidence scores")

    # Performance
    cache_results: bool = Field(default=True, description="Cache query results")
    timeout_seconds: int = Field(default=30, ge=1, description="Pipeline timeout")
    stream_response: bool = Field(default=False, description="Stream generation response")

    class Config:
        use_enum_values = True
        validate_assignment = True


class QueryRequest(BaseModel):
    """Request for query processing"""
    query: str = Field(..., min_length=1, description="User query")
    query_id: Optional[str] = Field(default=None, description="Unique query identifier")

    # Context
    user_id: Optional[str] = Field(default=None, description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    chat_history: Optional[List[Dict[str, str]]] = Field(default=None, description="Previous messages")

    # Configuration override
    pipeline_config: Optional[QueryPipelineConfig] = Field(default=None, description="Config override")

    # Filters
    document_filters: Optional[Dict[str, Any]] = Field(default=None, description="Document filters")
    date_range: Optional[Dict[str, datetime]] = Field(default=None, description="Date range filter")
    metadata_filters: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")

    # Options
    language: str = Field(default="en", description="Query language")
    return_intermediate: bool = Field(default=False, description="Return intermediate results")
    explain_results: bool = Field(default=False, description="Include explanations")

    class Config:
        validate_assignment = True


class RetrievalStageResult(BaseModel):
    """Result from retrieval stage"""
    query_embedding: Optional[List[float]] = Field(default=None, description="Query embedding")
    search_results: List[SearchResult] = Field(..., description="Retrieved results")
    total_results: int = Field(..., ge=0, description="Total matching results")

    # Metrics
    retrieval_time_ms: float = Field(..., ge=0, description="Retrieval time")
    embedding_time_ms: Optional[float] = Field(default=None, ge=0, description="Embedding generation time")

    # Search metadata
    search_strategy: SearchStrategy = Field(..., description="Strategy used")
    filters_applied: Optional[Dict[str, Any]] = Field(default=None, description="Applied filters")

    class Config:
        use_enum_values = True
        validate_assignment = True


class RerankingStageResult(BaseModel):
    """Result from reranking stage"""
    reranked_results: List[RerankedResult] = Field(..., description="Reranked results")
    reranking_time_ms: float = Field(..., ge=0, description="Reranking time")

    # Metrics
    score_improvement: float = Field(..., description="Average score improvement")
    reordering_distance: float = Field(..., ge=0, description="Reordering distance metric")

    # Model info
    reranker_model: str = Field(..., description="Reranker model used")

    class Config:
        validate_assignment = True


class GenerationStageResult(BaseModel):
    """Result from generation stage"""
    generated_answer: str = Field(..., description="Generated answer")
    generation_time_ms: float = Field(..., ge=0, description="Generation time")

    # Token usage
    prompt_tokens: int = Field(..., ge=0, description="Prompt tokens")
    completion_tokens: int = Field(..., ge=0, description="Completion tokens")
    total_tokens: int = Field(..., ge=0, description="Total tokens")

    # Model info
    model_used: str = Field(..., description="Model used for generation")
    temperature_used: float = Field(..., ge=0, le=2, description="Temperature used")

    # Sources
    sources_used: List[str] = Field(default_factory=list, description="Source IDs used")
    citations: Optional[List[Dict[str, Any]]] = Field(default=None, description="Source citations")

    class Config:
        validate_assignment = True


class QueryPipelineResult(BaseModel):
    """Complete result from query pipeline"""
    query_id: str = Field(..., description="Query identifier")
    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Final answer")

    # Stage results
    retrieval_result: Optional[RetrievalStageResult] = Field(default=None, description="Retrieval stage result")
    reranking_result: Optional[RerankingStageResult] = Field(default=None, description="Reranking stage result")
    generation_result: Optional[GenerationStageResult] = Field(default=None, description="Generation stage result")

    # Sources
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source documents")
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Answer confidence")

    # Timing
    total_time_ms: float = Field(..., ge=0, description="Total pipeline time")
    stage_times: Dict[str, float] = Field(default_factory=dict, description="Time per stage")

    # Metadata
    pipeline_config: QueryPipelineConfig = Field(..., description="Pipeline configuration used")
    timestamp: datetime = Field(default_factory=datetime.now, description="Query timestamp")

    # Errors and warnings
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")

    @validator("total_time_ms", always=True)
    def calculate_total_time(cls, v, values):
        """Calculate total time from stage times"""
        if "stage_times" in values and values["stage_times"]:
            return sum(values["stage_times"].values())
        return v or 0

    class Config:
        validate_assignment = True


class StreamingQueryResult(BaseModel):
    """Streaming query result chunk"""
    chunk_id: int = Field(..., ge=0, description="Chunk sequence number")
    chunk_type: Literal["answer", "source", "metadata", "complete"] = Field(..., description="Chunk type")

    # Content
    content: Optional[str] = Field(default=None, description="Chunk content")
    source: Optional[Dict[str, Any]] = Field(default=None, description="Source information")

    # Metadata
    is_final: bool = Field(default=False, description="Is final chunk")
    timestamp: datetime = Field(default_factory=datetime.now, description="Chunk timestamp")

    class Config:
        validate_assignment = True


class ConversationalContext(BaseModel):
    """Context for conversational queries"""
    session_id: str = Field(..., description="Conversation session ID")
    turn_count: int = Field(default=0, ge=0, description="Current turn number")

    # History
    message_history: List[Dict[str, str]] = Field(default_factory=list, description="Message history")
    context_window: int = Field(default=5, ge=1, description="Context window size")

    # State
    current_topic: Optional[str] = Field(default=None, description="Current conversation topic")
    entities_mentioned: List[str] = Field(default_factory=list, description="Mentioned entities")

    # Memory
    short_term_memory: Dict[str, Any] = Field(default_factory=dict, description="Short-term facts")
    long_term_memory: Optional[Dict[str, Any]] = Field(default=None, description="Long-term facts")

    def add_turn(self, query: str, answer: str) -> None:
        """Add a conversation turn"""
        self.message_history.append({"role": "user", "content": query})
        self.message_history.append({"role": "assistant", "content": answer})
        self.turn_count += 1

        # Maintain context window
        if len(self.message_history) > self.context_window * 2:
            self.message_history = self.message_history[-(self.context_window * 2):]

    class Config:
        validate_assignment = True


class MultiHopQuery(BaseModel):
    """Multi-hop reasoning query configuration"""
    initial_query: str = Field(..., description="Initial query")
    max_hops: int = Field(default=3, ge=1, le=5, description="Maximum reasoning hops")

    # Sub-queries
    sub_queries: List[str] = Field(default_factory=list, description="Generated sub-queries")
    hop_results: List[Dict[str, Any]] = Field(default_factory=list, description="Results from each hop")

    # Strategy
    reasoning_strategy: Literal["breadth_first", "depth_first", "best_first"] = Field(
        default="breadth_first",
        description="Reasoning strategy"
    )
    early_stopping: bool = Field(default=True, description="Stop when answer is found")

    # Constraints
    max_evidence_per_hop: int = Field(default=5, ge=1, description="Max evidence per hop")
    min_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Min confidence")

    class Config:
        validate_assignment = True


class QueryAnalytics(BaseModel):
    """Analytics for query processing"""
    # Query characteristics
    query_length: int = Field(..., ge=1, description="Query length in characters")
    query_tokens: int = Field(..., ge=1, description="Query token count")
    query_complexity: Literal["simple", "moderate", "complex"] = Field(..., description="Query complexity")

    # Performance metrics
    latency_ms: float = Field(..., ge=0, description="End-to-end latency")
    throughput_qps: float = Field(..., ge=0, description="Queries per second")

    # Quality metrics
    relevance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Answer relevance")
    completeness_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Answer completeness")
    accuracy_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Answer accuracy")

    # Usage metrics
    cache_hit: bool = Field(default=False, description="Cache hit for query")
    fallback_used: bool = Field(default=False, description="Fallback mechanism used")

    # User metrics
    user_satisfaction: Optional[float] = Field(default=None, ge=0.0, le=5.0, description="User rating")
    user_feedback: Optional[str] = Field(default=None, description="User feedback text")

    class Config:
        validate_assignment = True


class QueryOptimization(BaseModel):
    """Query optimization configuration"""
    # Query rewriting
    enable_query_expansion: bool = Field(default=False, description="Expand query with synonyms")
    enable_spell_correction: bool = Field(default=True, description="Correct spelling errors")
    enable_intent_detection: bool = Field(default=False, description="Detect query intent")

    # Caching
    cache_embeddings: bool = Field(default=True, description="Cache query embeddings")
    cache_results: bool = Field(default=True, description="Cache query results")
    cache_ttl_seconds: int = Field(default=3600, ge=1, description="Cache TTL")

    # Performance
    use_approximate_search: bool = Field(default=False, description="Use approximate nearest neighbor")
    early_termination: bool = Field(default=False, description="Terminate search early")
    parallel_retrieval: bool = Field(default=True, description="Parallel retrieval from sources")

    # Quality
    min_relevance_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Min relevance")
    diversity_factor: float = Field(default=0.0, ge=0.0, le=1.0, description="Result diversity")

    class Config:
        validate_assignment = True


class QueryFeedback(BaseModel):
    """User feedback for query results"""
    query_id: str = Field(..., description="Query identifier")

    # Ratings
    overall_rating: Optional[int] = Field(default=None, ge=1, le=5, description="Overall rating")
    relevance_rating: Optional[int] = Field(default=None, ge=1, le=5, description="Relevance rating")
    completeness_rating: Optional[int] = Field(default=None, ge=1, le=5, description="Completeness rating")

    # Feedback
    helpful: Optional[bool] = Field(default=None, description="Was the answer helpful")
    feedback_text: Optional[str] = Field(default=None, description="Text feedback")

    # Specific feedback
    missing_information: Optional[List[str]] = Field(default=None, description="Missing information")
    incorrect_information: Optional[List[str]] = Field(default=None, description="Incorrect information")
    preferred_sources: Optional[List[str]] = Field(default=None, description="Preferred source IDs")

    # Metadata
    user_id: Optional[str] = Field(default=None, description="User identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Feedback timestamp")

    class Config:
        validate_assignment = True


class QueryBatch(BaseModel):
    """Batch query processing request"""
    queries: List[QueryRequest] = Field(..., min_items=1, description="Queries to process")
    batch_id: str = Field(..., description="Batch identifier")

    # Processing options
    parallel: bool = Field(default=True, description="Process queries in parallel")
    max_parallel: int = Field(default=10, ge=1, description="Max parallel queries")

    # Configuration
    shared_config: Optional[QueryPipelineConfig] = Field(default=None, description="Shared configuration")
    deduplicate: bool = Field(default=True, description="Deduplicate similar queries")

    # Priority
    priority: int = Field(default=0, ge=0, le=10, description="Batch priority")

    class Config:
        validate_assignment = True


class QueryBatchResult(BaseModel):
    """Result from batch query processing"""
    batch_id: str = Field(..., description="Batch identifier")
    results: List[QueryPipelineResult] = Field(..., description="Individual query results")

    # Statistics
    total_queries: int = Field(..., ge=1, description="Total queries processed")
    successful: int = Field(..., ge=0, description="Successful queries")
    failed: int = Field(default=0, ge=0, description="Failed queries")

    # Performance
    total_time_ms: float = Field(..., ge=0, description="Total processing time")
    avg_query_time_ms: float = Field(..., ge=0, description="Average query time")

    # Deduplication
    unique_queries: int = Field(..., ge=1, description="Unique queries processed")
    duplicate_queries: int = Field(default=0, ge=0, description="Duplicate queries found")

    @validator("failed", always=True)
    def calculate_failed(cls, v, values):
        """Calculate failed count"""
        if "total_queries" in values and "successful" in values:
            return values["total_queries"] - values["successful"]
        return v or 0

    @validator("avg_query_time_ms", always=True)
    def calculate_avg_time(cls, v, values):
        """Calculate average query time"""
        if values.get("total_time_ms") and values.get("total_queries"):
            return values["total_time_ms"] / values["total_queries"]
        return v or 0

    class Config:
        validate_assignment = True