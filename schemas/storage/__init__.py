"""
Storage schemas for MinIO, Milvus, and caching
"""

# MinIO storage schemas
from schemas.storage.minio import (
    StorageOperation,
    BucketInfo,
    ObjectMetadata,
    DocumentStorage,
    ChunkStorage,
    StorageRequest,
    StorageResponse,
    StorageStats
)

# Milvus vector storage schemas
from schemas.storage.milvus import (
    IndexType,
    MetricType,
    FieldSchema,
    CollectionSchema,
    IndexConfig,
    VectorData,
    SearchRequest,
    SearchResult,
    CollectionStats,
    BulkInsertRequest,
    DeleteRequest
)

# Cache schemas
from schemas.storage.cache import (
    CacheType,
    CacheStrategy,
    CacheEntry,
    CacheConfig,
    CacheOperation,
    CacheStats,
    CacheBatch,
    CacheResult
)

__all__ = [
    # MinIO
    "StorageOperation",
    "BucketInfo",
    "ObjectMetadata",
    "DocumentStorage",
    "ChunkStorage",
    "StorageRequest",
    "StorageResponse",
    "StorageStats",
    # Milvus
    "IndexType",
    "MetricType",
    "FieldSchema",
    "CollectionSchema",
    "IndexConfig",
    "VectorData",
    "SearchRequest",
    "SearchResult",
    "CollectionStats",
    "BulkInsertRequest",
    "DeleteRequest",
    # Cache
    "CacheType",
    "CacheStrategy",
    "CacheEntry",
    "CacheConfig",
    "CacheOperation",
    "CacheStats",
    "CacheBatch",
    "CacheResult",
]


# Helper functions
def create_collection_schema(
    name: str,
    dimension: int = 1536,
    metric_type: MetricType = MetricType.COSINE,
    enable_dynamic_field: bool = True
) -> CollectionSchema:
    """
    Create a standard collection schema for RAG

    Args:
        name: Collection name
        dimension: Vector dimension
        metric_type: Distance metric
        enable_dynamic_field: Enable dynamic fields

    Returns:
        CollectionSchema configured for RAG use case
    """
    from schemas.storage.milvus import FieldSchema

    fields = [
        FieldSchema(
            name="id",
            dtype="VARCHAR",
            is_primary=True,
            auto_id=False,
            max_length=64
        ),
        FieldSchema(
            name="embedding",
            dtype="FLOAT_VECTOR",
            dim=dimension
        ),
        FieldSchema(
            name="chunk_text",
            dtype="VARCHAR",
            max_length=65535
        ),
        FieldSchema(
            name="document_id",
            dtype="VARCHAR",
            max_length=255
        ),
        FieldSchema(
            name="page_number",
            dtype="INT64"
        ),
        FieldSchema(
            name="chunk_index",
            dtype="INT64"
        ),
        FieldSchema(
            name="metadata",
            dtype="JSON"
        )
    ]

    return CollectionSchema(
        name=name,
        fields=fields,
        enable_dynamic_field=enable_dynamic_field,
        description="RAG collection for document chunks"
    )


def create_search_request(
    collection_name: str,
    query_vector: list[float],
    top_k: int = 10,
    filter_expr: str = None,
    output_fields: list[str] = None
) -> SearchRequest:
    """
    Create a search request with common defaults

    Args:
        collection_name: Collection to search
        query_vector: Query embedding
        top_k: Number of results
        filter_expr: Optional filter expression
        output_fields: Fields to return

    Returns:
        SearchRequest configured for typical RAG search
    """
    if output_fields is None:
        output_fields = ["id", "chunk_text", "document_id", "page_number", "metadata"]

    return SearchRequest(
        collection_name=collection_name,
        vector=query_vector,
        top_k=top_k,
        filter_expr=filter_expr,
        output_fields=output_fields,
        search_params={"ef": 64}
    )


def create_cache_config(
    cache_type: CacheType = CacheType.MEMORY,
    max_size_mb: int = 100,
    default_ttl_hours: int = 1
) -> CacheConfig:
    """
    Create cache configuration with defaults

    Args:
        cache_type: Type of cache backend
        max_size_mb: Maximum cache size in MB
        default_ttl_hours: Default TTL in hours

    Returns:
        CacheConfig with sensible defaults
    """
    return CacheConfig(
        cache_type=cache_type,
        max_size_mb=max_size_mb,
        default_ttl_seconds=default_ttl_hours * 3600,
        max_ttl_seconds=default_ttl_hours * 3600 * 24,  # 24x the default
        strategy=CacheStrategy.LRU
    )