"""
MinIO configuration schema
"""
from pydantic import BaseModel, Field, validator
from typing import Optional


class MinIOSettings(BaseModel):
    """MinIO object storage configuration"""

    endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    access_key: str = Field(default="minioadmin", description="MinIO access key")
    secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    secure: bool = Field(default=False, description="Use HTTPS connection")

    # Bucket configuration
    bucket_docs: str = Field(default="raw-documents", description="Bucket for raw documents")
    bucket_chunks: str = Field(default="rag-chunks", description="Bucket for processed chunks")

    # Storage settings
    region: Optional[str] = Field(default=None, description="MinIO region")
    part_size: int = Field(default=5 * 1024 * 1024, description="Part size for multipart uploads")

    # Connection settings
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    # Performance settings
    enable_checksum: bool = Field(default=True, description="Enable checksum validation")
    thread_pool_size: int = Field(default=10, description="Thread pool size for concurrent operations")

    @validator("endpoint")
    def validate_endpoint(cls, v):
        """Validate endpoint format"""
        if not v:
            raise ValueError("Endpoint cannot be empty")
        if v.startswith("http://") or v.startswith("https://"):
            raise ValueError("Endpoint should not include protocol (http/https)")
        return v

    @validator("part_size")
    def validate_part_size(cls, v):
        """Validate part size is within MinIO limits"""
        min_size = 5 * 1024 * 1024  # 5MB
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        if v < min_size or v > max_size:
            raise ValueError(f"Part size must be between {min_size} and {max_size} bytes")
        return v

    class Config:
        validate_assignment = True