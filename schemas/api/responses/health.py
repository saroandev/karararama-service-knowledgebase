"""
Health check response schemas
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class MilvusStatus(BaseModel):
    """Milvus service status"""
    status: str = Field(..., description="Connection status: connected/disconnected")
    message: str = Field(..., description="Status message")
    server_version: Optional[str] = Field(None, description="Milvus server version")
    collections_count: Optional[int] = Field(None, description="Total number of collections")


class MinioStatus(BaseModel):
    """MinIO service status"""
    status: str = Field(..., description="Connection status: connected/disconnected")
    message: str = Field(..., description="Status message")


class GlobalDBStatus(BaseModel):
    """OneDocs Global DB service status"""
    status: str = Field(..., description="Connection status: connected/disconnected")
    message: str = Field(..., description="Status message")
    url: Optional[str] = Field(None, description="Global DB service URL")


class ServiceStatus(BaseModel):
    """Individual service status"""
    milvus: MilvusStatus = Field(..., description="Milvus service status")
    minio: MinioStatus = Field(..., description="MinIO service status")
    global_db: GlobalDBStatus = Field(..., description="OneDocs Global DB service status")
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
                        "message": "Connected to Milvus server v2.6.1",
                        "server_version": "2.6.1",
                        "collections_count": 5
                    },
                    "minio": {
                        "status": "connected",
                        "message": "Connected to MinIO"
                    },
                    "global_db": {
                        "status": "connected",
                        "message": "Connected to Global DB service",
                        "url": "http://localhost:8070"
                    },
                    "embedding_model": "text-embedding-3-small",
                    "embedding_dimension": 1536
                },
                "version": "2.0.0"
            }
        }
    }
