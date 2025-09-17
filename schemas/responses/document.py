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
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "doc_abc123",
                "title": "Introduction to RAG",
                "chunks_count": 15,
                "created_at": "2024-01-15T10:30:00",
                "file_hash": "5d41402abc4b2a76b9719d911017c592",
                "metadata": {
                    "pages": 10,
                    "category": "technical"
                }
        }
            }
        }
