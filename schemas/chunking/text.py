"""
Text chunking specific schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from schemas.chunking.base import ChunkingConfig, ChunkingMethod


class TextChunkConfig(ChunkingConfig):
    """Configuration for text-based chunking"""
    method: Literal[ChunkingMethod.TOKEN, ChunkingMethod.CHARACTER] = Field(
        default=ChunkingMethod.TOKEN,
        description="Text chunking method"
    )

    # Token-specific settings
    encoding_name: str = Field(
        default="cl100k_base",
        description="Tokenizer encoding (cl100k_base for GPT-4, p50k_base for GPT-3)"
    )

    # Character-specific settings
    split_on_whitespace: bool = Field(
        default=True,
        description="Split on whitespace boundaries when using character chunking"
    )

    # Sentence preservation
    preserve_sentences: bool = Field(
        default=True,
        description="Try to keep complete sentences together"
    )
    sentence_endings: List[str] = Field(
        default_factory=lambda: [".", "!", "?", "。", "！", "？"],
        description="Characters that mark sentence endings"
    )

    # Paragraph preservation
    preserve_paragraphs: bool = Field(
        default=False,
        description="Try to keep paragraphs together"
    )
    paragraph_separator: str = Field(
        default="\n\n",
        description="String that separates paragraphs"
    )

    # Special handling
    remove_empty_chunks: bool = Field(
        default=True,
        description="Remove chunks that are empty or only whitespace"
    )
    normalize_whitespace: bool = Field(
        default=True,
        description="Normalize multiple spaces/newlines to single space"
    )

    class Config:
        use_enum_values = True


class TextChunkResult(BaseModel):
    """Result from text chunking operation"""
    chunk_text: str = Field(..., description="The chunked text")
    start_position: int = Field(..., ge=0, description="Start position in original text")
    end_position: int = Field(..., ge=0, description="End position in original text")

    # Token information (if applicable)
    token_ids: Optional[List[int]] = Field(
        default=None,
        description="Token IDs if using token-based chunking"
    )

    # Boundary information
    starts_with_sentence: bool = Field(
        default=True,
        description="Whether chunk starts at sentence boundary"
    )
    ends_with_sentence: bool = Field(
        default=True,
        description="Whether chunk ends at sentence boundary"
    )

    # Overlap information
    overlap_with_previous: int = Field(
        default=0,
        ge=0,
        description="Number of tokens/chars overlapping with previous chunk"
    )
    overlap_with_next: int = Field(
        default=0,
        ge=0,
        description="Number of tokens/chars overlapping with next chunk"
    )

    @validator("end_position")
    def validate_positions(cls, v, values):
        """Ensure end position is after start position"""
        if "start_position" in values and v <= values["start_position"]:
            raise ValueError("End position must be greater than start position")
        return v

    class Config:
        validate_assignment = True


class TextChunkingStrategy(BaseModel):
    """Strategy for text chunking"""
    primary_method: ChunkingMethod = Field(
        default=ChunkingMethod.TOKEN,
        description="Primary chunking method"
    )

    fallback_method: Optional[ChunkingMethod] = Field(
        default=ChunkingMethod.CHARACTER,
        description="Fallback method if primary fails"
    )

    # Advanced strategies
    use_sliding_window: bool = Field(
        default=True,
        description="Use sliding window approach for overlap"
    )

    adaptive_sizing: bool = Field(
        default=False,
        description="Adaptively adjust chunk size based on content"
    )

    min_adaptive_size: Optional[int] = Field(
        default=100,
        description="Minimum size when using adaptive sizing"
    )

    max_adaptive_size: Optional[int] = Field(
        default=1000,
        description="Maximum size when using adaptive sizing"
    )

    @validator("fallback_method")
    def validate_fallback(cls, v, values):
        """Ensure fallback is different from primary"""
        if v and "primary_method" in values and v == values["primary_method"]:
            raise ValueError("Fallback method must be different from primary method")
        return v

    class Config:
        use_enum_values = True