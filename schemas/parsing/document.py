"""
Document-related schemas for parsing operations
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


@dataclass
class DocumentMetadata:
    """Comprehensive document metadata for parsing and processing"""
    # Core identification
    document_id: Optional[str] = None
    original_filename: Optional[str] = None
    file_hash: Optional[str] = None

    # Document properties
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None

    # Timestamps
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None

    # Document structure
    page_count: int = 0
    total_pages: int = 0  # Alias for compatibility
    file_size: int = 0
    document_hash: Optional[str] = None  # Alias for compatibility

    # Additional metadata
    custom_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Sync aliases for backward compatibility"""
        if self.total_pages and not self.page_count:
            self.page_count = self.total_pages
        elif self.page_count and not self.total_pages:
            self.total_pages = self.page_count

        if self.document_hash and not self.file_hash:
            self.file_hash = self.document_hash
        elif self.file_hash and not self.document_hash:
            self.document_hash = self.file_hash


class DocumentProcessingResult(BaseModel):
    """Result of document processing operation"""
    document_id: str = Field(..., description="Document identifier")
    status: str = Field(..., description="Processing status", pattern="^(success|failed|partial)$")
    chunks_created: int = Field(default=0, description="Number of chunks created")
    pages_processed: int = Field(default=0, description="Number of pages processed")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    processing_time: float = Field(..., description="Total processing time in seconds")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "doc_abc123",
                "status": "success",
                "chunks_created": 15,
                "pages_processed": 10,
                "errors": [],
                "warnings": ["Page 5 contains mostly images, text extraction limited"],
                "processing_time": 3.45
            }
        }
    }