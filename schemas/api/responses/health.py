"""
Health check response schemas
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class MilvusStatus(BaseModel):
    """Milvus service status"""
    status: str = Field(..., description="Connection status: connected/disconnected")
    message: str = Field(..., description="Status message")
    collection: Optional[str] = Field(None, description="Active collection name")
    entities: Optional[int] = Field(None, description="Number of entities in collection")


class MinioStatus(BaseModel):
    """MinIO service status"""
    status: str = Field(..., description="Connection status: connected/disconnected")
    message: str = Field(..., description="Status message")


class ServiceStatus(BaseModel):
    """Individual service status"""
    milvus: MilvusStatus = Field(..., description="Milvus service status")
    minio: MinioStatus = Field(..., description="MinIO service status")
    embedding_model: str = Field(..., description="Active embedding model")
    embedding_dimension: int = Field(..., description="Embedding dimension")


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Overall system status")
    timestamp: str = Field(..., description="Check timestamp")
    services: ServiceStatus = Field(..., description="Individual service statuses")
    version: str = Field(..., description="API version")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00",
                "services": {
                    "milvus": {
                        "status": "connected",
                        "message": "Connected to collection 'rag_chunks'",
                        "collection": "rag_chunks",
                        "entities": 1000
                    },
                    "minio": {
                        "status": "connected",
                        "message": "Connected to MinIO"
                    },
                    "embedding_model": "text-embedding-3-small",
                    "embedding_dimension": 1536
                },
                "version": "2.0.0"
            }
        }
    }
