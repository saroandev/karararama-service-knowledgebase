"""
Semantic chunking schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from schemas.chunking.base import ChunkingConfig, ChunkingMethod


class SemanticChunkConfig(ChunkingConfig):
    """Configuration for semantic-based chunking"""
    method: Literal[ChunkingMethod.SEMANTIC] = Field(
        default=ChunkingMethod.SEMANTIC,
        description="Semantic chunking method"
    )

    # Embedding model settings
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Model to use for generating embeddings"
    )

    # Similarity settings
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for grouping"
    )

    similarity_metric: Literal["cosine", "euclidean", "manhattan"] = Field(
        default="cosine",
        description="Similarity metric to use"
    )

    # Grouping settings
    min_group_size: int = Field(
        default=100,
        ge=10,
        description="Minimum size for a semantic group"
    )

    max_group_size: int = Field(
        default=1000,
        ge=100,
        description="Maximum size for a semantic group"
    )

    # Boundary detection
    use_sentence_boundaries: bool = Field(
        default=True,
        description="Respect sentence boundaries when chunking"
    )

    use_paragraph_boundaries: bool = Field(
        default=True,
        description="Respect paragraph boundaries when chunking"
    )

    # Advanced settings
    buffer_size: int = Field(
        default=5,
        ge=1,
        description="Number of sentences to buffer for similarity comparison"
    )

    combine_short_chunks: bool = Field(
        default=True,
        description="Combine very short semantic chunks"
    )

    @validator("max_group_size")
    def validate_group_sizes(cls, v, values):
        """Ensure max is greater than min"""
        if "min_group_size" in values and v <= values["min_group_size"]:
            raise ValueError("Max group size must be greater than min group size")
        return v

    class Config:
        use_enum_values = True


class SemanticChunkResult(BaseModel):
    """Result from semantic chunking"""
    chunk_text: str = Field(..., description="The chunked text")
    semantic_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average semantic coherence score"
    )

    # Semantic group information
    group_id: str = Field(..., description="Semantic group identifier")
    group_theme: Optional[str] = Field(
        default=None,
        description="Detected theme or topic of the group"
    )

    # Embedding information
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Embedding vector for the chunk"
    )

    centroid_distance: Optional[float] = Field(
        default=None,
        description="Distance from group centroid"
    )

    # Boundary scores
    start_boundary_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for start boundary"
    )

    end_boundary_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for end boundary"
    )

    # Related chunks
    similar_chunk_ids: List[str] = Field(
        default_factory=list,
        description="IDs of semantically similar chunks"
    )

    class Config:
        validate_assignment = True


class SemanticAnalysis(BaseModel):
    """Semantic analysis results for chunking decisions"""
    text_segment: str = Field(..., description="Text segment being analyzed")

    # Semantic features
    main_topics: List[str] = Field(
        default_factory=list,
        description="Main topics detected in segment"
    )

    entities: List[str] = Field(
        default_factory=list,
        description="Named entities found"
    )

    sentiment: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Sentiment score (-1 to 1)"
    )

    # Coherence metrics
    internal_coherence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Internal semantic coherence"
    )

    transition_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Score for transition to next segment"
    )

    # Structural features
    is_complete_thought: bool = Field(
        default=True,
        description="Whether segment represents a complete thought"
    )

    has_topic_shift: bool = Field(
        default=False,
        description="Whether there's a topic shift at the end"
    )

    class Config:
        validate_assignment = True


class SemanticChunkingStrategy(BaseModel):
    """Strategy for semantic chunking"""
    algorithm: Literal["hierarchical", "sliding_window", "topic_modeling"] = Field(
        default="sliding_window",
        description="Semantic chunking algorithm"
    )

    # Preprocessing
    preprocess_text: bool = Field(
        default=True,
        description="Apply text preprocessing before chunking"
    )

    remove_stopwords: bool = Field(
        default=False,
        description="Remove stopwords for semantic analysis"
    )

    # Postprocessing
    rebalance_chunks: bool = Field(
        default=True,
        description="Rebalance chunk sizes after semantic grouping"
    )

    merge_similar_groups: bool = Field(
        default=False,
        description="Merge highly similar semantic groups"
    )

    class Config:
        use_enum_values = True