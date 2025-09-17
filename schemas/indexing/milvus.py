"""
Milvus vector database indexing schemas.
Provides comprehensive schemas for index configuration, management, and operations.
"""

from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ConfigDict


# Enums for index and metric types
class IndexType(str, Enum):
    """Milvus index types"""
    FLAT = "FLAT"
    IVF_FLAT = "IVF_FLAT"
    IVF_SQ8 = "IVF_SQ8"
    IVF_PQ = "IVF_PQ"
    HNSW = "HNSW"
    SCANN = "SCANN"
    ANNOY = "ANNOY"
    DISKANN = "DISKANN"
    GPU_IVF_FLAT = "GPU_IVF_FLAT"
    GPU_IVF_PQ = "GPU_IVF_PQ"


class MetricType(str, Enum):
    """Distance metric types"""
    L2 = "L2"
    IP = "IP"  # Inner Product
    COSINE = "COSINE"
    JACCARD = "JACCARD"
    HAMMING = "HAMMING"
    TANIMOTO = "TANIMOTO"


class ConsistencyLevel(str, Enum):
    """Consistency level for operations"""
    STRONG = "Strong"
    SESSION = "Session"
    BOUNDED = "Bounded"
    EVENTUALLY = "Eventually"
    CUSTOMIZED = "Customized"


class IndexState(str, Enum):
    """Index building state"""
    NOT_EXIST = "NotExist"
    UNISSUED = "Unissued"
    IN_PROGRESS = "InProgress"
    FINISHED = "Finished"
    FAILED = "Failed"
    RETRY = "Retry"


# Index configuration schemas
class IndexParams(BaseModel):
    """Parameters for specific index types"""
    model_config = ConfigDict(extra='allow')

    # Common parameters
    nlist: Optional[int] = Field(None, description="Number of cluster units")
    nprobe: Optional[int] = Field(None, description="Number of units to query")

    # HNSW specific
    M: Optional[int] = Field(None, description="HNSW: Maximum degree of nodes")
    efConstruction: Optional[int] = Field(None, description="HNSW: Size of dynamic candidate list")
    ef: Optional[int] = Field(None, description="HNSW: Search scope")

    # IVF_PQ specific
    m: Optional[int] = Field(None, description="IVF_PQ: Number of sub-vectors")
    nbits: Optional[int] = Field(None, description="IVF_PQ: Bits per sub-vector")

    # DiskANN specific
    search_list: Optional[int] = Field(None, description="DiskANN: Size of candidate list")

    @field_validator('nlist', 'nprobe', 'M', 'efConstruction', 'ef', 'm', 'nbits', 'search_list')
    @classmethod
    def validate_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Parameter must be positive")
        return v


class IndexConfig(BaseModel):
    """Complete index configuration"""
    index_type: IndexType = Field(default=IndexType.HNSW, description="Type of index to build")
    metric_type: MetricType = Field(default=MetricType.COSINE, description="Distance metric")
    params: IndexParams = Field(default_factory=IndexParams, description="Index-specific parameters")

    @model_validator(mode='after')
    def validate_params_for_index_type(self):
        """Validate parameters match the index type"""
        index_type = self.index_type
        params = self.params

        if index_type == IndexType.HNSW:
            if not params.M:
                params.M = 16
            if not params.efConstruction:
                params.efConstruction = 200
        elif index_type in [IndexType.IVF_FLAT, IndexType.IVF_SQ8]:
            if not params.nlist:
                params.nlist = 128
        elif index_type == IndexType.IVF_PQ:
            if not params.nlist:
                params.nlist = 128
            if not params.m:
                params.m = 8
            if not params.nbits:
                params.nbits = 8

        return self


class IndexStatus(BaseModel):
    """Status of an index"""
    collection_name: str = Field(description="Name of the collection")
    field_name: str = Field(description="Field with the index")
    index_type: Optional[IndexType] = Field(None, description="Type of index")
    metric_type: Optional[MetricType] = Field(None, description="Distance metric")
    state: IndexState = Field(default=IndexState.NOT_EXIST, description="Current state")
    progress: Optional[float] = Field(None, ge=0, le=100, description="Building progress percentage")
    total_rows: Optional[int] = Field(None, description="Total number of rows")
    indexed_rows: Optional[int] = Field(None, description="Number of indexed rows")
    pending_index_rows: Optional[int] = Field(None, description="Rows pending indexing")
    error_message: Optional[str] = Field(None, description="Error if failed")
    created_at: Optional[datetime] = Field(None, description="Index creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")


# Collection management schemas
class FieldSchema(BaseModel):
    """Schema for a collection field"""
    name: str = Field(description="Field name")
    dtype: str = Field(description="Data type")
    is_primary: bool = Field(default=False, description="Is primary key")
    is_partition_key: bool = Field(default=False, description="Is partition key")
    auto_id: bool = Field(default=False, description="Auto-generate IDs")
    max_length: Optional[int] = Field(None, description="Max length for VARCHAR")
    dim: Optional[int] = Field(None, description="Dimension for vector fields")
    description: Optional[str] = Field(None, description="Field description")


class CollectionConfig(BaseModel):
    """Configuration for creating a collection"""
    name: str = Field(description="Collection name")
    fields: List[FieldSchema] = Field(description="Field definitions")
    description: Optional[str] = Field(None, description="Collection description")
    consistency_level: ConsistencyLevel = Field(
        default=ConsistencyLevel.SESSION,
        description="Consistency level"
    )
    enable_dynamic_field: bool = Field(default=False, description="Enable dynamic fields")
    num_shards: int = Field(default=2, ge=1, description="Number of shards")
    properties: Optional[Dict[str, Any]] = Field(None, description="Additional properties")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Collection name cannot be empty")
        if len(v) > 255:
            raise ValueError("Collection name too long")
        return v


class PartitionConfig(BaseModel):
    """Configuration for partitions"""
    collection_name: str = Field(description="Collection name")
    partition_name: str = Field(description="Partition name")
    description: Optional[str] = Field(None, description="Partition description")

    @field_validator('partition_name')
    @classmethod
    def validate_partition_name(cls, v):
        if not v or v == "_default":
            raise ValueError("Invalid partition name")
        return v


# Indexing operation schemas
class IndexingRequest(BaseModel):
    """Request for indexing chunks"""
    collection_name: str = Field(description="Target collection")
    chunks: List[Dict[str, Any]] = Field(description="Chunks to index")
    embeddings: List[List[float]] = Field(description="Embedding vectors")
    partition_name: Optional[str] = Field(None, description="Target partition")
    consistency_level: Optional[ConsistencyLevel] = Field(None, description="Consistency level")

    @model_validator(mode='after')
    def validate_matching_lengths(self):
        if len(self.chunks) != len(self.embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
        return self


class IndexingResult(BaseModel):
    """Result of indexing operation"""
    success: bool = Field(description="Operation success")
    collection_name: str = Field(description="Collection name")
    num_indexed: int = Field(default=0, description="Number of indexed items")
    num_failed: int = Field(default=0, description="Number of failed items")
    failed_ids: Optional[List[str]] = Field(None, description="IDs that failed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    duration_ms: Optional[float] = Field(None, description="Operation duration")
    index_status: Optional[IndexStatus] = Field(None, description="Current index status")


class BatchIndexingRequest(BaseModel):
    """Request for batch indexing"""
    collection_name: str = Field(description="Target collection")
    batches: List[IndexingRequest] = Field(description="Batch of indexing requests")
    parallel_processing: bool = Field(default=False, description="Process batches in parallel")
    max_batch_size: int = Field(default=1000, ge=1, description="Maximum batch size")


class BatchIndexingResult(BaseModel):
    """Result of batch indexing"""
    success: bool = Field(description="Overall success")
    total_indexed: int = Field(description="Total indexed items")
    total_failed: int = Field(description="Total failed items")
    batch_results: List[IndexingResult] = Field(description="Individual batch results")
    duration_ms: Optional[float] = Field(None, description="Total duration")


# Search and filter schemas
class SearchExpression(BaseModel):
    """Milvus search filter expression"""
    field: str = Field(description="Field to filter on")
    operator: str = Field(description="Comparison operator")
    value: Union[str, int, float, List[Any]] = Field(description="Value to compare")

    def to_expression(self) -> str:
        """Convert to Milvus expression string"""
        if self.operator == "in":
            if isinstance(self.value, list):
                values = [f'"{v}"' if isinstance(v, str) else str(v) for v in self.value]
                return f'{self.field} in [{", ".join(values)}]'
        elif self.operator == "==":
            if isinstance(self.value, str):
                return f'{self.field} == "{self.value}"'
            return f'{self.field} == {self.value}'
        elif self.operator in [">", ">=", "<", "<="]:
            return f'{self.field} {self.operator} {self.value}'
        else:
            raise ValueError(f"Unsupported operator: {self.operator}")


class CompoundExpression(BaseModel):
    """Compound search expression with AND/OR"""
    expressions: List[Union[SearchExpression, 'CompoundExpression']] = Field(description="Sub-expressions")
    operator: str = Field(default="and", description="Logical operator (and/or)")

    def to_expression(self) -> str:
        """Convert to Milvus expression string"""
        sub_exprs = [expr.to_expression() for expr in self.expressions]
        return f' {self.operator} '.join(f'({expr})' for expr in sub_exprs)


# Index optimization schemas
class IndexOptimization(BaseModel):
    """Index optimization configuration"""
    collection_name: str = Field(description="Collection to optimize")
    compact: bool = Field(default=False, description="Perform compaction")
    rebuild_index: bool = Field(default=False, description="Rebuild index")
    balance_segments: bool = Field(default=False, description="Balance segments")
    flush: bool = Field(default=True, description="Flush data to disk")
    target_segment_size_mb: Optional[int] = Field(None, description="Target segment size")


class OptimizationResult(BaseModel):
    """Result of optimization operation"""
    success: bool = Field(description="Operation success")
    collection_name: str = Field(description="Collection name")
    operations_performed: List[str] = Field(description="Operations that were performed")
    segments_before: Optional[int] = Field(None, description="Segments before optimization")
    segments_after: Optional[int] = Field(None, description="Segments after optimization")
    duration_ms: Optional[float] = Field(None, description="Operation duration")
    error_message: Optional[str] = Field(None, description="Error if failed")


# Metrics and monitoring
class IndexingMetrics(BaseModel):
    """Metrics for indexing operations"""
    collection_name: str = Field(description="Collection name")
    total_vectors: int = Field(description="Total number of vectors")
    indexed_vectors: int = Field(description="Number of indexed vectors")
    indexing_rate: float = Field(description="Vectors per second")
    memory_usage_mb: float = Field(description="Memory usage in MB")
    disk_usage_mb: float = Field(description="Disk usage in MB")
    last_indexed_at: Optional[datetime] = Field(None, description="Last indexing time")
    average_latency_ms: Optional[float] = Field(None, description="Average indexing latency")
    p95_latency_ms: Optional[float] = Field(None, description="95th percentile latency")
    p99_latency_ms: Optional[float] = Field(None, description="99th percentile latency")


# Collection statistics
class CollectionStats(BaseModel):
    """Statistics for a collection"""
    name: str = Field(description="Collection name")
    row_count: int = Field(description="Total number of rows")
    loaded: bool = Field(description="Is collection loaded")
    indexed: bool = Field(description="Has index")
    partitions: List[str] = Field(default_factory=list, description="Partition names")
    segments: int = Field(default=0, description="Number of segments")
    index_configs: Optional[List[IndexConfig]] = Field(None, description="Index configurations")
    memory_usage_mb: Optional[float] = Field(None, description="Memory usage")
    disk_usage_mb: Optional[float] = Field(None, description="Disk usage")


# Helper functions
def create_index_config(
    index_type: str = "HNSW",
    metric_type: str = "COSINE",
    **params
) -> IndexConfig:
    """
    Create an index configuration with defaults.

    Args:
        index_type: Type of index
        metric_type: Distance metric
        **params: Additional parameters

    Returns:
        IndexConfig instance
    """
    index_params = IndexParams(**params)

    # Set defaults based on index type
    if index_type == "HNSW" and not params:
        index_params.M = 16
        index_params.efConstruction = 200
    elif index_type in ["IVF_FLAT", "IVF_SQ8"] and not params:
        index_params.nlist = 128

    return IndexConfig(
        index_type=IndexType(index_type),
        metric_type=MetricType(metric_type),
        params=index_params
    )


def get_default_index_params(index_type: str) -> Dict[str, Any]:
    """
    Get default parameters for an index type.

    Args:
        index_type: Type of index

    Returns:
        Dictionary of default parameters
    """
    defaults = {
        "FLAT": {},
        "IVF_FLAT": {"nlist": 128, "nprobe": 16},
        "IVF_SQ8": {"nlist": 128, "nprobe": 16},
        "IVF_PQ": {"nlist": 128, "m": 8, "nbits": 8, "nprobe": 16},
        "HNSW": {"M": 16, "efConstruction": 200, "ef": 64},
        "SCANN": {"nlist": 128, "with_raw_data": True},
        "ANNOY": {"n_trees": 8},
        "DISKANN": {"search_list": 100}
    }

    return defaults.get(index_type.upper(), {})


def validate_collection_schema(fields: List[FieldSchema]) -> bool:
    """
    Validate a collection schema.

    Args:
        fields: List of field schemas

    Returns:
        True if valid

    Raises:
        ValueError: If schema is invalid
    """
    # Check for primary key
    primary_keys = [f for f in fields if f.is_primary]
    if len(primary_keys) != 1:
        raise ValueError("Collection must have exactly one primary key")

    # Check for at least one vector field
    vector_fields = [f for f in fields if f.dim is not None]
    if not vector_fields:
        raise ValueError("Collection must have at least one vector field")

    # Check field names are unique
    names = [f.name for f in fields]
    if len(names) != len(set(names)):
        raise ValueError("Field names must be unique")

    return True


def create_search_expression(filters: Dict[str, Any]) -> str:
    """
    Create a Milvus search expression from filters.

    Args:
        filters: Dictionary of field:value filters

    Returns:
        Milvus expression string
    """
    expressions = []

    for field, value in filters.items():
        if isinstance(value, dict):
            # Handle operator-based filters
            operator = value.get("operator", "==")
            val = value.get("value")
            expr = SearchExpression(field=field, operator=operator, value=val)
        else:
            # Simple equality filter
            expr = SearchExpression(field=field, operator="==", value=value)

        expressions.append(expr.to_expression())

    return " and ".join(expressions)


# Re-export for convenience
__all__ = [
    # Enums
    "IndexType",
    "MetricType",
    "ConsistencyLevel",
    "IndexState",
    # Index configuration
    "IndexParams",
    "IndexConfig",
    "IndexStatus",
    # Collection management
    "FieldSchema",
    "CollectionConfig",
    "PartitionConfig",
    # Indexing operations
    "IndexingRequest",
    "IndexingResult",
    "BatchIndexingRequest",
    "BatchIndexingResult",
    # Search and filters
    "SearchExpression",
    "CompoundExpression",
    # Optimization
    "IndexOptimization",
    "OptimizationResult",
    # Metrics
    "IndexingMetrics",
    "CollectionStats",
    # Helper functions
    "create_index_config",
    "get_default_index_params",
    "validate_collection_schema",
    "create_search_expression",
]