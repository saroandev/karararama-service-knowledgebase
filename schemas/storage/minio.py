"""
MinIO storage operation schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from enum import Enum


class StorageOperation(str, Enum):
    """Storage operation types"""
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DELETE = "delete"
    LIST = "list"
    MOVE = "move"
    COPY = "copy"


class BucketInfo(BaseModel):
    """MinIO bucket information"""
    name: str = Field(..., description="Bucket name")
    creation_date: Optional[datetime] = Field(default=None, description="Bucket creation date")

    # Bucket configuration
    versioning_enabled: bool = Field(default=False, description="Versioning enabled")
    encryption_enabled: bool = Field(default=False, description="Encryption enabled")

    # Storage metrics
    total_size: Optional[int] = Field(default=None, ge=0, description="Total size in bytes")
    object_count: Optional[int] = Field(default=None, ge=0, description="Number of objects")

    # Access control
    public: bool = Field(default=False, description="Public access enabled")
    policy: Optional[Dict[str, Any]] = Field(default=None, description="Bucket policy")

    @validator("name")
    def validate_bucket_name(cls, v):
        """Validate bucket name follows MinIO conventions"""
        if not v:
            raise ValueError("Bucket name cannot be empty")
        if len(v) < 3 or len(v) > 63:
            raise ValueError("Bucket name must be between 3 and 63 characters")
        if not v[0].isalnum() or not v[-1].isalnum():
            raise ValueError("Bucket name must start and end with alphanumeric character")
        return v.lower()

    class Config:
        validate_assignment = True


class ObjectMetadata(BaseModel):
    """Metadata for stored objects"""
    bucket: str = Field(..., description="Bucket name")
    object_name: str = Field(..., description="Object key/name")
    size: int = Field(..., ge=0, description="Object size in bytes")

    # Timestamps
    last_modified: datetime = Field(..., description="Last modification time")
    upload_date: Optional[datetime] = Field(default=None, description="Upload timestamp")

    # Content information
    content_type: str = Field(default="application/octet-stream", description="MIME type")
    etag: Optional[str] = Field(default=None, description="Entity tag for cache validation")

    # Custom metadata
    metadata: Dict[str, str] = Field(default_factory=dict, description="Custom metadata")
    tags: Dict[str, str] = Field(default_factory=dict, description="Object tags")

    # Version information
    version_id: Optional[str] = Field(default=None, description="Version ID if versioning enabled")
    is_latest: bool = Field(default=True, description="Is latest version")

    class Config:
        validate_assignment = True


class DocumentStorage(BaseModel):
    """Schema for document storage operations"""
    document_id: str = Field(..., description="Unique document identifier")
    file_name: str = Field(..., description="Original file name")
    file_path: str = Field(..., description="Storage path in bucket")

    # File information
    file_size: int = Field(..., ge=0, description="File size in bytes")
    file_type: str = Field(..., description="File MIME type")
    file_hash: str = Field(..., description="File hash for integrity")

    # Storage location
    bucket: str = Field(..., description="Storage bucket")
    region: Optional[str] = Field(default=None, description="Storage region")

    # Processing information
    processed: bool = Field(default=False, description="Has been processed")
    processing_date: Optional[datetime] = Field(default=None, description="Processing timestamp")
    chunk_count: Optional[int] = Field(default=None, ge=0, description="Number of chunks created")

    # Access information
    public_url: Optional[str] = Field(default=None, description="Public URL if available")
    signed_url: Optional[str] = Field(default=None, description="Temporary signed URL")
    expires_at: Optional[datetime] = Field(default=None, description="URL expiration time")

    class Config:
        validate_assignment = True


class ChunkStorage(BaseModel):
    """Schema for chunk storage operations"""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")

    # Storage information
    storage_path: str = Field(..., description="Path in storage")
    bucket: str = Field(..., description="Storage bucket")

    # Content
    text_content: str = Field(..., description="Chunk text content")
    content_size: int = Field(..., ge=0, description="Content size in bytes")

    # Metadata
    chunk_index: int = Field(..., ge=0, description="Chunk index in document")
    page_number: Optional[int] = Field(default=None, ge=1, description="Page number if applicable")

    # Embedding information
    has_embedding: bool = Field(default=False, description="Whether embedding is stored")
    embedding_path: Optional[str] = Field(default=None, description="Path to embedding file")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    updated_at: Optional[datetime] = Field(default=None, description="Last update time")

    class Config:
        validate_assignment = True


class StorageRequest(BaseModel):
    """Request for storage operations"""
    operation: StorageOperation = Field(..., description="Operation type")
    bucket: str = Field(..., description="Target bucket")

    # Object information
    object_name: Optional[str] = Field(default=None, description="Object key/name")
    object_names: Optional[List[str]] = Field(default=None, description="Multiple object names")

    # Operation parameters
    source_bucket: Optional[str] = Field(default=None, description="Source bucket for copy/move")
    destination_bucket: Optional[str] = Field(default=None, description="Destination bucket")

    # Options
    recursive: bool = Field(default=False, description="Recursive operation")
    force: bool = Field(default=False, description="Force operation")
    create_bucket: bool = Field(default=False, description="Create bucket if not exists")

    # Filters
    prefix: Optional[str] = Field(default=None, description="Object name prefix filter")
    suffix: Optional[str] = Field(default=None, description="Object name suffix filter")

    @validator("object_names")
    def validate_object_names(cls, v, values):
        """Ensure single object name or multiple, not both"""
        if v and "object_name" in values and values["object_name"]:
            raise ValueError("Cannot specify both object_name and object_names")
        return v

    class Config:
        use_enum_values = True


class StorageResponse(BaseModel):
    """Response from storage operations"""
    success: bool = Field(..., description="Operation success status")
    operation: StorageOperation = Field(..., description="Operation performed")

    # Result information
    message: Optional[str] = Field(default=None, description="Result message")
    object_url: Optional[str] = Field(default=None, description="Object URL if applicable")

    # Affected objects
    affected_count: int = Field(default=0, ge=0, description="Number of objects affected")
    affected_objects: List[str] = Field(default_factory=list, description="List of affected objects")

    # Errors
    errors: List[str] = Field(default_factory=list, description="Error messages if any")
    partial_success: bool = Field(default=False, description="Whether partially successful")

    # Performance metrics
    duration_ms: Optional[float] = Field(default=None, ge=0, description="Operation duration in ms")
    bytes_transferred: Optional[int] = Field(default=None, ge=0, description="Bytes transferred")

    class Config:
        use_enum_values = True


class StorageStats(BaseModel):
    """Storage statistics and metrics"""
    total_buckets: int = Field(..., ge=0, description="Total number of buckets")
    total_objects: int = Field(..., ge=0, description="Total number of objects")
    total_size_bytes: int = Field(..., ge=0, description="Total storage size in bytes")

    # Breakdown by type
    documents_count: int = Field(default=0, ge=0, description="Number of documents")
    chunks_count: int = Field(default=0, ge=0, description="Number of chunks")
    embeddings_count: int = Field(default=0, ge=0, description="Number of embeddings")

    # Size breakdown
    documents_size: int = Field(default=0, ge=0, description="Total documents size")
    chunks_size: int = Field(default=0, ge=0, description="Total chunks size")
    embeddings_size: int = Field(default=0, ge=0, description="Total embeddings size")

    # Usage metrics
    bandwidth_used: Optional[int] = Field(default=None, ge=0, description="Bandwidth used in bytes")
    api_calls: Optional[int] = Field(default=None, ge=0, description="Number of API calls")

    # Quotas
    storage_quota: Optional[int] = Field(default=None, ge=0, description="Storage quota in bytes")
    usage_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Usage percentage")

    # Timestamp
    calculated_at: datetime = Field(default_factory=datetime.now, description="Calculation time")

    class Config:
        validate_assignment = True