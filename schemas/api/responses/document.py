"""
Document response schemas
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    """Document information response model"""
    document_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    chunks_count: int = Field(..., description="Number of chunks")
    created_at: str = Field(..., description="Creation timestamp")
    file_hash: str = Field(..., description="MD5 hash of the file")
    size_bytes: int = Field(0, description="Document size in bytes")
    size_mb: float = Field(0.0, description="Document size in megabytes")
    document_type: str = Field("PDF", description="Document file type (e.g., PDF, DOCX)")
    uploaded_by: str = Field(..., description="User ID who uploaded the document")
    uploaded_by_email: Optional[str] = Field(None, description="Email of the uploader")
    collection_name: Optional[str] = Field(None, description="Collection name if document is in a collection")
    url: Optional[str] = Field(default=None, description="MinIO presigned URL for document download")
    scope: Optional[str] = Field(default=None, description="Data scope: private or shared")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "doc_abc123",
                "title": "Introduction to RAG",
                "chunks_count": 15,
                "created_at": "2024-01-15T10:30:00",
                "file_hash": "5d41402abc4b2a76b9719d911017c592",
                "size_bytes": 2048000,
                "size_mb": 1.95,
                "document_type": "PDF",
                "uploaded_by": "17d0faab-0830-4007-8ed6-73cfd049505b",
                "uploaded_by_email": "user@example.com",
                "collection_name": "legal-research",
                "url": "https://minio.example.com/...",
                "scope": "private",
                "metadata": {
                    "pages": 10,
                    "category": "technical"
                }
        }
            }
        }
