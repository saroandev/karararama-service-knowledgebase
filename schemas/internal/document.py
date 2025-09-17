"""
Document schemas for internal data processing
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


@dataclass
class DocumentMetadata:
    """Document metadata for internal processing"""
    document_id: str
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    total_pages: int = 0
    file_hash: str = ""
    original_filename: str = ""
    custom_metadata: Optional[Dict[str, Any]] = None


class DocumentProcessingResult(BaseModel):
    """Result of document processing operation"""
    document_id: str = Field(..., description="Document identifier")
    status: str = Field(..., description="Processing status", pattern="^(success|failed|partial)$")
    chunks_created: int = Field(default=0, description="Number of chunks created")
    pages_processed: int = Field(default=0, description="Number of pages processed")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    processing_time: float = Field(..., description="Total processing time in seconds")

    class Config:
        schema_extra = {
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