"""
Chunk schemas for internal data processing
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


@dataclass
class SimpleChunk:
    """Simple chunk dataclass for internal processing"""
    chunk_id: str
    text: str
    page_number: int
    chunk_index: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ChunkMetadata(BaseModel):
    """Metadata for document chunks"""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    page_number: int = Field(..., description="Page number in document")
    chunk_index: int = Field(..., description="Chunk index in document")
    minio_object_path: str = Field(..., description="MinIO storage path")
    document_title: str = Field(..., description="Parent document title")
    file_hash: str = Field(..., description="Document file hash")
    created_at: int = Field(..., description="Creation timestamp (milliseconds)")
    embedding_model: str = Field(..., description="Embedding model used")
    embedding_dimension: int = Field(..., description="Embedding vector dimension")
    embedding_size_bytes: int = Field(..., description="Embedding size in bytes")

    model_config = {
        "json_schema_extra": {
            "example": {
                "chunk_id": "doc_123_0001",
                "page_number": 1,
                "chunk_index": 0,
                "minio_object_path": "doc_123/doc_123_0001.json",
                "document_title": "Sample Document",
                "file_hash": "5d41402abc4b2a76b9719d911017c592",
                "created_at": 1705316400000,
                "embedding_model": "text-embedding-3-small",
                "embedding_dimension": 1536,
                "embedding_size_bytes": 6144
            }
        }
        }
