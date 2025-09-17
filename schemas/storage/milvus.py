"""
Milvus vector storage schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal, Union
from datetime import datetime
from enum import Enum


class IndexType(str, Enum):
    """Milvus index types"""
    FLAT = "FLAT"
    IVF_FLAT = "IVF_FLAT"
    IVF_SQ8 = "IVF_SQ8"
    IVF_PQ = "IVF_PQ"
    HNSW = "HNSW"
    ANNOY = "ANNOY"
    DISKANN = "DISKANN"


class MetricType(str, Enum):
    """Distance metric types"""
    L2 = "L2"
    IP = "IP"  # Inner Product
    COSINE = "COSINE"
    JACCARD = "JACCARD"
    HAMMING = "HAMMING"
    TANIMOTO = "TANIMOTO"


class FieldSchema(BaseModel):
    """Schema for collection fields"""
    name: str = Field(..., description="Field name")
    dtype: Literal[
        "BOOL", "INT8", "INT16", "INT32", "INT64",
        "FLOAT", "DOUBLE", "VARCHAR", "JSON",
        "FLOAT_VECTOR", "BINARY_VECTOR"
    ] = Field(..., description="Data type")

    # Field properties
    is_primary: bool = Field(default=False, description="Is primary key")
    auto_id: bool = Field(default=False, description="Auto-generate ID")
    is_partition_key: bool = Field(default=False, description="Is partition key")

    # Constraints
    max_length: Optional[int] = Field(default=None, description="Max length for VARCHAR")
    dim: Optional[int] = Field(default=None, description="Dimension for vector fields")

    # Default value
    default_value: Optional[Any] = Field(default=None, description="Default value")
    description: Optional[str] = Field(default=None, description="Field description")

    @validator("dim")
    def validate_dimension(cls, v, values):
        """Validate dimension for vector fields"""
        if "dtype" in values and "VECTOR" in values["dtype"] and not v:
            raise ValueError("Vector fields must specify dimension")
        return v

    @validator("max_length")
    def validate_max_length(cls, v, values):
        """Validate max_length for VARCHAR fields"""
        if "dtype" in values and values["dtype"] == "VARCHAR" and not v:
            raise ValueError("VARCHAR fields must specify max_length")
        return v

    class Config:
        use_enum_values = True


class CollectionSchema(BaseModel):
    """Schema for Milvus collection"""
    name: str = Field(..., description="Collection name")
    description: Optional[str] = Field(default=None, description="Collection description")

    # Fields
    fields: List[FieldSchema] = Field(..., description="Collection fields")

    # Collection properties
    enable_dynamic_field: bool = Field(default=False, description="Enable dynamic fields")
    num_shards: int = Field(default=2, ge=1, description="Number of shards")
    num_replicas: int = Field(default=1, ge=1, description="Number of replicas")

    # Consistency level
    consistency_level: Literal["Strong", "Session", "Bounded", "Eventually"] = Field(
        default="Session",
        description="Consistency level"
    )

    @validator("fields")
    def validate_fields(cls, v):
        """Validate collection has required fields"""
        has_primary = any(f.is_primary for f in v)
        if not has_primary:
            raise ValueError("Collection must have a primary key field")

        has_vector = any("VECTOR" in f.dtype for f in v)
        if not has_vector:
            raise ValueError("Collection must have at least one vector field")

        return v

    class Config:
        validate_assignment = True


class IndexConfig(BaseModel):
    """Configuration for vector index"""
    field_name: str = Field(..., description="Field to index")
    index_type: IndexType = Field(default=IndexType.HNSW, description="Index type")
    metric_type: MetricType = Field(default=MetricType.COSINE, description="Distance metric")

    # Index parameters
    index_params: Dict[str, Any] = Field(
        default_factory=lambda: {"M": 8, "efConstruction": 64},
        description="Index-specific parameters"
    )

    # Build parameters
    build_immediately: bool = Field(default=True, description="Build index immediately")

    @validator("index_params")
    def validate_params(cls, v, values):
        """Validate parameters for specific index types"""
        if "index_type" not in values:
            return v

        index_type = values["index_type"]
        if index_type == IndexType.HNSW:
            if "M" not in v or "efConstruction" not in v:
                raise ValueError("HNSW requires M and efConstruction parameters")
        elif index_type in [IndexType.IVF_FLAT, IndexType.IVF_SQ8]:
            if "nlist" not in v:
                raise ValueError(f"{index_type} requires nlist parameter")

        return v

    class Config:
        use_enum_values = True


class VectorData(BaseModel):
    """Schema for vector data storage"""
    id: Union[str, int] = Field(..., description="Vector ID")
    vector: List[float] = Field(..., description="Vector embedding")

    # Associated data
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata fields")

    # Chunk information
    chunk_text: Optional[str] = Field(default=None, description="Text content")
    document_id: Optional[str] = Field(default=None, description="Parent document ID")
    chunk_index: Optional[int] = Field(default=None, description="Chunk index")
    page_number: Optional[int] = Field(default=None, description="Page number")

    @validator("vector")
    def validate_vector(cls, v):
        """Validate vector is not empty"""
        if not v:
            raise ValueError("Vector cannot be empty")
        return v

    class Config:
        validate_assignment = True


class SearchRequest(BaseModel):
    """Request for vector search"""
    collection_name: str = Field(..., description="Collection to search")
    vector: List[float] = Field(..., description="Query vector")

    # Search parameters
    top_k: int = Field(default=10, ge=1, le=16384, description="Number of results")
    metric_type: Optional[MetricType] = Field(default=None, description="Distance metric")

    # Filter expression
    filter_expr: Optional[str] = Field(default=None, description="Filter expression")

    # Output fields
    output_fields: List[str] = Field(
        default_factory=lambda: ["id", "chunk_text", "document_id"],
        description="Fields to return"
    )

    # Search parameters
    search_params: Dict[str, Any] = Field(
        default_factory=lambda: {"ef": 64},
        description="Search-specific parameters"
    )

    # Advanced options
    consistency_level: Optional[str] = Field(default=None, description="Consistency level")
    guarantee_timestamp: Optional[int] = Field(default=None, description="Guarantee timestamp")
    travel_timestamp: Optional[int] = Field(default=None, description="Travel timestamp")

    class Config:
        use_enum_values = True


class SearchResult(BaseModel):
    """Result from vector search"""
    id: Union[str, int] = Field(..., description="Result ID")
    score: float = Field(..., description="Similarity score")
    distance: Optional[float] = Field(default=None, description="Distance value")

    # Retrieved fields
    fields: Dict[str, Any] = Field(default_factory=dict, description="Retrieved fields")

    # Convenience accessors
    chunk_text: Optional[str] = Field(default=None, description="Chunk text if available")
    document_id: Optional[str] = Field(default=None, description="Document ID if available")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata if available")

    class Config:
        validate_assignment = True


class CollectionStats(BaseModel):
    """Statistics for a collection"""
    collection_name: str = Field(..., description="Collection name")

    # Size metrics
    entity_count: int = Field(..., ge=0, description="Number of entities")
    indexed_count: int = Field(..., ge=0, description="Number of indexed entities")

    # Storage metrics
    memory_usage_bytes: int = Field(..., ge=0, description="Memory usage in bytes")
    disk_usage_bytes: Optional[int] = Field(default=None, ge=0, description="Disk usage in bytes")

    # Index information
    has_index: bool = Field(..., description="Whether collection has index")
    index_type: Optional[IndexType] = Field(default=None, description="Index type if exists")
    index_progress: Optional[float] = Field(default=None, ge=0, le=100, description="Index build progress")

    # Shard information
    num_shards: int = Field(..., ge=1, description="Number of shards")
    loaded_shards: int = Field(..., ge=0, description="Number of loaded shards")

    # Status
    loaded: bool = Field(..., description="Whether collection is loaded")
    consistency_level: str = Field(..., description="Consistency level")

    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    class Config:
        use_enum_values = True


class BulkInsertRequest(BaseModel):
    """Request for bulk insert operation"""
    collection_name: str = Field(..., description="Target collection")
    data: List[VectorData] = Field(..., description="Data to insert")

    # Options
    partition_name: Optional[str] = Field(default=None, description="Target partition")
    timeout: Optional[float] = Field(default=None, description="Operation timeout")

    @validator("data")
    def validate_data(cls, v):
        """Validate data is not empty"""
        if not v:
            raise ValueError("Data cannot be empty for bulk insert")
        return v

    class Config:
        validate_assignment = True


class DeleteRequest(BaseModel):
    """Request for delete operation"""
    collection_name: str = Field(..., description="Collection name")

    # Delete by expression or IDs
    expr: Optional[str] = Field(default=None, description="Delete expression")
    ids: Optional[List[Union[str, int]]] = Field(default=None, description="IDs to delete")

    # Options
    partition_name: Optional[str] = Field(default=None, description="Target partition")
    timeout: Optional[float] = Field(default=None, description="Operation timeout")

    @validator("ids")
    def validate_delete_params(cls, v, values):
        """Ensure either expr or ids is provided"""
        if not v and not values.get("expr"):
            raise ValueError("Either expr or ids must be provided for delete")
        if v and values.get("expr"):
            raise ValueError("Cannot specify both expr and ids")
        return v

    class Config:
        validate_assignment = True