"""
Document-specific chunking schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from schemas.chunking.base import ChunkingConfig, ChunkingMethod


class DocumentChunkConfig(ChunkingConfig):
    """Configuration for document-aware chunking"""
    method: Literal[ChunkingMethod.DOCUMENT] = Field(
        default=ChunkingMethod.DOCUMENT,
        description="Document chunking method"
    )

    # Document structure settings
    preserve_pages: bool = Field(
        default=True,
        description="Keep page boundaries intact"
    )

    preserve_sections: bool = Field(
        default=True,
        description="Keep document sections together"
    )

    preserve_tables: bool = Field(
        default=True,
        description="Keep tables as single chunks"
    )

    preserve_lists: bool = Field(
        default=True,
        description="Keep lists together"
    )

    # Heading detection
    detect_headings: bool = Field(
        default=True,
        description="Detect and use document headings"
    )

    heading_patterns: List[str] = Field(
        default_factory=lambda: [
            r"^#{1,6}\s+",  # Markdown headings
            r"^\d+\.\s+",    # Numbered headings
            r"^[A-Z][A-Z\s]+$",  # All caps headings
        ],
        description="Regex patterns for heading detection"
    )

    # Size constraints per element type
    max_section_size: int = Field(
        default=2000,
        ge=100,
        description="Maximum size for a section chunk"
    )

    max_table_size: int = Field(
        default=1500,
        ge=100,
        description="Maximum size for a table chunk"
    )

    max_list_size: int = Field(
        default=1000,
        ge=100,
        description="Maximum size for a list chunk"
    )

    # Metadata extraction
    extract_metadata: bool = Field(
        default=True,
        description="Extract document metadata"
    )

    metadata_fields: List[str] = Field(
        default_factory=lambda: ["title", "author", "date", "section", "page"],
        description="Metadata fields to extract"
    )

    class Config:
        use_enum_values = True


class DocumentElement(BaseModel):
    """Represents a structural element in a document"""
    element_type: Literal[
        "heading", "paragraph", "table", "list",
        "image", "code_block", "footnote", "caption"
    ] = Field(..., description="Type of document element")

    content: str = Field(..., description="Element content")

    # Hierarchy information
    level: Optional[int] = Field(
        default=None,
        ge=1,
        le=6,
        description="Hierarchy level (e.g., heading level)"
    )

    parent_id: Optional[str] = Field(
        default=None,
        description="Parent element ID"
    )

    # Position information
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Page number in document"
    )

    position_in_page: Optional[int] = Field(
        default=None,
        ge=0,
        description="Position within page"
    )

    # Styling information
    style: Dict[str, Any] = Field(
        default_factory=dict,
        description="Style attributes (font, size, etc.)"
    )

    # Relationships
    references: List[str] = Field(
        default_factory=list,
        description="References to other elements"
    )

    class Config:
        use_enum_values = True


class DocumentStructure(BaseModel):
    """Document structure analysis"""
    document_id: str = Field(..., description="Document identifier")

    # Document metadata
    title: Optional[str] = Field(default=None, description="Document title")
    author: Optional[str] = Field(default=None, description="Document author")
    creation_date: Optional[str] = Field(default=None, description="Creation date")

    # Structure
    total_pages: int = Field(..., ge=1, description="Total number of pages")
    total_sections: int = Field(..., ge=0, description="Number of sections")

    # Table of contents
    toc: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Table of contents structure"
    )

    # Document elements
    elements: List[DocumentElement] = Field(
        default_factory=list,
        description="All document elements"
    )

    # Statistics
    word_count: int = Field(..., ge=0, description="Total word count")
    table_count: int = Field(default=0, ge=0, description="Number of tables")
    image_count: int = Field(default=0, ge=0, description="Number of images")
    list_count: int = Field(default=0, ge=0, description="Number of lists")

    class Config:
        validate_assignment = True


class DocumentChunkResult(BaseModel):
    """Result from document-aware chunking"""
    chunk_text: str = Field(..., description="The chunked text")

    # Document context
    section_title: Optional[str] = Field(
        default=None,
        description="Section this chunk belongs to"
    )

    section_number: Optional[str] = Field(
        default=None,
        description="Section number/identifier"
    )

    page_range: tuple[int, int] = Field(
        ...,
        description="Page range (start, end)"
    )

    # Element types in chunk
    element_types: List[str] = Field(
        default_factory=list,
        description="Types of elements in this chunk"
    )

    # Structural importance
    importance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Importance score based on document structure"
    )

    is_heading: bool = Field(
        default=False,
        description="Whether chunk is primarily a heading"
    )

    is_summary: bool = Field(
        default=False,
        description="Whether chunk appears to be a summary"
    )

    # Navigation
    previous_section: Optional[str] = Field(
        default=None,
        description="Previous section title"
    )

    next_section: Optional[str] = Field(
        default=None,
        description="Next section title"
    )

    @validator("page_range")
    def validate_page_range(cls, v):
        """Ensure valid page range"""
        if v[1] < v[0]:
            raise ValueError("End page must be >= start page")
        return v

    class Config:
        validate_assignment = True