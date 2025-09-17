"""
Hybrid chunking schemas
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Literal
from schemas.chunking.base import ChunkingConfig, ChunkingMethod


class HybridChunkConfig(ChunkingConfig):
    """Configuration for hybrid chunking approach"""
    method: Literal[ChunkingMethod.HYBRID] = Field(
        default=ChunkingMethod.HYBRID,
        description="Hybrid chunking method"
    )

    # Primary and secondary methods
    primary_method: ChunkingMethod = Field(
        default=ChunkingMethod.SEMANTIC,
        description="Primary chunking method"
    )

    secondary_method: ChunkingMethod = Field(
        default=ChunkingMethod.TOKEN,
        description="Secondary/fallback chunking method"
    )

    # Method weights
    method_weights: Dict[ChunkingMethod, float] = Field(
        default_factory=lambda: {
            ChunkingMethod.SEMANTIC: 0.6,
            ChunkingMethod.TOKEN: 0.4,
        },
        description="Weights for combining methods"
    )

    # Combination strategy
    combination_strategy: Literal["weighted", "voting", "cascade", "adaptive"] = Field(
        default="weighted",
        description="How to combine multiple methods"
    )

    # Adaptive settings
    adaptive_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold for adaptive method switching"
    )

    # Conflict resolution
    on_conflict: Literal["primary", "secondary", "merge", "split"] = Field(
        default="merge",
        description="How to handle conflicts between methods"
    )

    # Refinement
    refine_boundaries: bool = Field(
        default=True,
        description="Refine chunk boundaries after initial chunking"
    )

    balance_sizes: bool = Field(
        default=True,
        description="Balance chunk sizes across methods"
    )

    @validator("secondary_method")
    def validate_methods(cls, v, values):
        """Ensure primary and secondary are different"""
        if "primary_method" in values and v == values["primary_method"]:
            raise ValueError("Secondary method must be different from primary")
        return v

    @validator("method_weights")
    def validate_weights(cls, v):
        """Ensure weights sum to approximately 1.0"""
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Method weights must sum to 1.0, got {total}")
        return v

    class Config:
        use_enum_values = True


class HybridChunkResult(BaseModel):
    """Result from hybrid chunking operation"""
    chunk_text: str = Field(..., description="The chunked text")

    # Method contributions
    primary_contribution: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Contribution from primary method"
    )

    secondary_contribution: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Contribution from secondary method"
    )

    methods_used: List[ChunkingMethod] = Field(
        ...,
        description="Methods that contributed to this chunk"
    )

    # Boundary decisions
    boundary_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in chunk boundaries"
    )

    boundary_agreement: bool = Field(
        default=True,
        description="Whether methods agreed on boundaries"
    )

    # Quality metrics
    coherence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall coherence score"
    )

    balance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Size balance score"
    )

    # Refinement info
    was_refined: bool = Field(
        default=False,
        description="Whether chunk was refined"
    )

    refinement_details: Optional[str] = Field(
        default=None,
        description="Details of refinement if applied"
    )

    class Config:
        validate_assignment = True
        use_enum_values = True


class HybridChunkingStrategy(BaseModel):
    """Advanced strategy for hybrid chunking"""

    # Method selection
    auto_select_methods: bool = Field(
        default=False,
        description="Automatically select best methods based on content"
    )

    available_methods: List[ChunkingMethod] = Field(
        default_factory=lambda: [
            ChunkingMethod.SEMANTIC,
            ChunkingMethod.TOKEN,
            ChunkingMethod.DOCUMENT,
        ],
        description="Pool of methods to choose from"
    )

    # Performance optimization
    parallel_processing: bool = Field(
        default=False,
        description="Process methods in parallel"
    )

    cache_intermediate: bool = Field(
        default=True,
        description="Cache intermediate results"
    )

    # Quality control
    min_quality_score: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality score"
    )

    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum refinement iterations"
    )

    # Fallback
    fallback_to_simple: bool = Field(
        default=True,
        description="Fall back to simple chunking if hybrid fails"
    )

    class Config:
        use_enum_values = True


class HybridAnalysis(BaseModel):
    """Analysis results from hybrid chunking"""
    document_id: str = Field(..., description="Document analyzed")

    # Method performance
    method_scores: Dict[ChunkingMethod, float] = Field(
        ...,
        description="Performance score for each method"
    )

    optimal_combination: List[ChunkingMethod] = Field(
        ...,
        description="Optimal method combination found"
    )

    # Quality metrics
    overall_quality: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall chunking quality"
    )

    consistency_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Consistency across chunks"
    )

    # Recommendations
    recommended_config: Optional[HybridChunkConfig] = Field(
        default=None,
        description="Recommended configuration for this content type"
    )

    improvement_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions for improvement"
    )

    class Config:
        validate_assignment = True
        use_enum_values = True