"""
Base schemas for chunking operations
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime


class ChunkingMethod(str, Enum):
    """Enumeration of available chunking methods"""
    TOKEN = "token"
    CHARACTER = "character"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"
    DOCUMENT = "document"
    HYBRID = "hybrid"


class ChunkMetadata(BaseModel):
    """Metadata associated with a chunk"""
    page_number: Optional[int] = Field(default=None, description="Page number if from document")
    section: Optional[str] = Field(default=None, description="Section or chapter title")
    source_file: Optional[str] = Field(default=None, description="Source file name")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    language: Optional[str] = Field(default=None, description="Language of the text")

    # Statistics
    sentence_count: Optional[int] = Field(default=None, description="Number of sentences")
    word_count: Optional[int] = Field(default=None, description="Number of words")

    # Additional custom metadata
    custom: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True


class Chunk(BaseModel):
    """Schema for a text chunk"""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document identifier")
    chunk_index: int = Field(..., ge=0, description="Sequential index within document")
    text: str = Field(..., min_length=1, description="Chunk text content")

    # Size metrics
    token_count: int = Field(..., ge=0, description="Number of tokens in chunk")
    char_count: int = Field(..., ge=0, description="Number of characters in chunk")

    # Metadata
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata, description="Chunk metadata")

    # Optional embedding
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding of chunk")

    @validator("chunk_id")
    def validate_chunk_id(cls, v, values):
        """Ensure chunk_id follows expected format"""
        if not v and "document_id" in values and "chunk_index" in values:
            return f"{values['document_id']}_chunk_{values['chunk_index']:04d}"
        return v

    @validator("char_count", always=True)
    def validate_char_count(cls, v, values):
        """Auto-calculate char_count if not provided"""
        if v == 0 and "text" in values:
            return len(values["text"])
        return v

    class Config:
        validate_assignment = True
        use_enum_values = True


class ChunkingConfig(BaseModel):
    """Configuration for chunking operations"""
    method: ChunkingMethod = Field(default=ChunkingMethod.TOKEN, description="Chunking method")
    chunk_size: int = Field(default=512, ge=50, le=2000, description="Target chunk size")
    chunk_overlap: int = Field(default=50, ge=0, description="Overlap between chunks")

    # Method-specific settings
    preserve_sentences: bool = Field(default=True, description="Try to preserve sentence boundaries")
    preserve_paragraphs: bool = Field(default=False, description="Try to preserve paragraph boundaries")
    preserve_pages: bool = Field(default=False, description="Preserve page boundaries in documents")

    # Token chunking settings
    encoding_name: str = Field(default="cl100k_base", description="Tokenizer encoding name")

    # Semantic chunking settings
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold for semantic chunking")

    @validator("chunk_overlap")
    def validate_overlap(cls, v, values):
        """Ensure overlap is less than chunk size"""
        if "chunk_size" in values and v >= values["chunk_size"]:
            raise ValueError("Chunk overlap must be less than chunk size")
        return v

    class Config:
        use_enum_values = True


class ChunkingResult(BaseModel):
    """Result of a chunking operation"""
    document_id: str = Field(..., description="Document that was chunked")
    chunks: List[Chunk] = Field(..., description="Generated chunks")
    total_chunks: int = Field(..., ge=0, description="Total number of chunks")
    total_tokens: int = Field(..., ge=0, description="Total tokens across all chunks")
    total_chars: int = Field(..., ge=0, description="Total characters across all chunks")
    method_used: ChunkingMethod = Field(..., description="Chunking method used")
    config: ChunkingConfig = Field(..., description="Configuration used for chunking")

    # Processing metrics
    processing_time: Optional[float] = Field(default=None, description="Time taken in seconds")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")

    @validator("total_chunks", always=True)
    def calculate_total_chunks(cls, v, values):
        """Auto-calculate total chunks"""
        if v == 0 and "chunks" in values:
            return len(values["chunks"])
        return v

    @validator("total_tokens", always=True)
    def calculate_total_tokens(cls, v, values):
        """Auto-calculate total tokens"""
        if v == 0 and "chunks" in values:
            return sum(chunk.token_count for chunk in values["chunks"])
        return v

    @validator("total_chars", always=True)
    def calculate_total_chars(cls, v, values):
        """Auto-calculate total characters"""
        if v == 0 and "chunks" in values:
            return sum(chunk.char_count for chunk in values["chunks"])
        return v

    class Config:
        validate_assignment = True
        use_enum_values = True