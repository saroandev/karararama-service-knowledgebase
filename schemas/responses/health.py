"""
Health check response schemas
"""
from typing import Dict, Any
from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    """Individual service status"""
    milvus: str = Field(..., description="Milvus connection status")
    minio: str = Field(..., description="MinIO connection status")
    collection: str = Field(..., description="Active collection name")
    entities: int = Field(..., description="Number of entities in collection")
    embedding_model: str = Field(..., description="Active embedding model")
    embedding_dimension: int = Field(..., description="Embedding dimension")


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Overall system status")
    timestamp: str = Field(..., description="Check timestamp")
    services: ServiceStatus = Field(..., description="Individual service statuses")
    version: str = Field(..., description="API version")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00",
                "services": {
                    "milvus": "connected",
                    "minio": "connected",
                    "collection": "rag_chunks_1536",
                    "entities": 1000,
                    "embedding_model": "text-embedding-3-small",
                    "embedding_dimension": 1536
                },
                "version": "2.0.0"
            }
        }