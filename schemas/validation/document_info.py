"""
Document information schemas for validation
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document types"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"


class ContentInfo(BaseModel):
    """Information about document content"""
    has_tables: bool = False
    table_count: int = 0
    has_images: bool = False
    image_count: int = 0
    has_links: bool = False
    link_count: int = 0
    has_forms: bool = False
    form_count: int = 0

    # Text statistics
    word_count: int = 0
    char_count: int = 0
    line_count: int = 0
    paragraph_count: int = 0

    # Page statistics
    page_count: int = 0
    empty_page_count: int = 0
    page_density: float = Field(default=0.0, description="Average words per page")

    # Content quality indicators
    requires_ocr: bool = False
    has_encryption: bool = False
    has_watermarks: bool = False

    # Additional metadata
    detected_languages: list[str] = Field(default_factory=list)
    encoding: str = "utf-8"


class DocumentInfo(BaseModel):
    """Complete document information"""
    document_type: DocumentType
    file_name: str
    file_size: int  # bytes
    file_extension: str
    mime_type: Optional[str] = None

    # Content analysis
    content_info: ContentInfo

    # Processing hints
    processing_hints: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True