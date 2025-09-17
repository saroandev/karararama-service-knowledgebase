"""
Cache storage schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Any, Dict, List, Literal
from datetime import datetime, timedelta
from enum import Enum


class CacheType(str, Enum):
    """Types of cache storage"""
    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"
    HYBRID = "hybrid"


class CacheStrategy(str, Enum):
    """Cache eviction strategies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live based


class CacheEntry(BaseModel):
    """Schema for cached items"""
    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Cached value")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    accessed_at: datetime = Field(default_factory=datetime.now, description="Last access time")
    updated_at: Optional[datetime] = Field(default=None, description="Last update time")

    # TTL
    ttl_seconds: Optional[int] = Field(default=None, ge=1, description="Time to live in seconds")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")

    # Usage statistics
    access_count: int = Field(default=0, ge=0, description="Number of accesses")
    hit_count: int = Field(default=0, ge=0, description="Number of cache hits")

    # Size information
    size_bytes: Optional[int] = Field(default=None, ge=0, description="Size in bytes")

    # Tags for grouping
    tags: List[str] = Field(default_factory=list, description="Cache tags")
    namespace: Optional[str] = Field(default=None, description="Cache namespace")

    @validator("expires_at", always=True)
    def calculate_expiration(cls, v, values):
        """Calculate expiration time from TTL if not set"""
        if not v and "ttl_seconds" in values and values["ttl_seconds"]:
            created_at = values.get("created_at", datetime.now())
            return created_at + timedelta(seconds=values["ttl_seconds"])
        return v

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False

    class Config:
        validate_assignment = True
        arbitrary_types_allowed = True


class CacheConfig(BaseModel):
    """Configuration for cache system"""
    cache_type: CacheType = Field(default=CacheType.MEMORY, description="Cache backend type")
    strategy: CacheStrategy = Field(default=CacheStrategy.LRU, description="Eviction strategy")

    # Size limits
    max_size_mb: int = Field(default=100, ge=1, description="Maximum cache size in MB")
    max_entries: int = Field(default=10000, ge=1, description="Maximum number of entries")

    # TTL settings
    default_ttl_seconds: int = Field(default=3600, ge=1, description="Default TTL in seconds")
    max_ttl_seconds: int = Field(default=86400, ge=1, description="Maximum TTL in seconds")

    # Redis settings (if applicable)
    redis_host: Optional[str] = Field(default="localhost", description="Redis host")
    redis_port: Optional[int] = Field(default=6379, description="Redis port")
    redis_db: Optional[int] = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")

    # Disk cache settings
    disk_path: Optional[str] = Field(default="/tmp/cache", description="Disk cache path")

    # Performance settings
    enable_compression: bool = Field(default=False, description="Enable value compression")
    enable_encryption: bool = Field(default=False, description="Enable value encryption")

    # Monitoring
    enable_stats: bool = Field(default=True, description="Enable statistics collection")
    stats_interval_seconds: int = Field(default=60, description="Stats collection interval")

    @validator("max_ttl_seconds")
    def validate_ttl(cls, v, values):
        """Ensure max TTL is greater than default TTL"""
        if "default_ttl_seconds" in values and v < values["default_ttl_seconds"]:
            raise ValueError("Max TTL must be greater than or equal to default TTL")
        return v

    class Config:
        use_enum_values = True


class CacheOperation(BaseModel):
    """Schema for cache operations"""
    operation: Literal["get", "set", "delete", "clear", "exists"] = Field(..., description="Operation type")
    key: Optional[str] = Field(default=None, description="Cache key")
    keys: Optional[List[str]] = Field(default=None, description="Multiple cache keys")

    # For set operation
    value: Optional[Any] = Field(default=None, description="Value to cache")
    ttl_seconds: Optional[int] = Field(default=None, description="TTL for this entry")

    # Options
    namespace: Optional[str] = Field(default=None, description="Cache namespace")
    tags: Optional[List[str]] = Field(default=None, description="Tags for the entry")

    # Conditional operations
    if_not_exists: bool = Field(default=False, description="Only set if not exists")
    if_exists: bool = Field(default=False, description="Only operate if exists")

    @validator("keys")
    def validate_keys(cls, v, values):
        """Ensure single key or multiple keys, not both"""
        if v and values.get("key"):
            raise ValueError("Cannot specify both key and keys")
        return v

    class Config:
        validate_assignment = True


class CacheStats(BaseModel):
    """Cache statistics and metrics"""
    cache_type: CacheType = Field(..., description="Cache backend type")

    # Size metrics
    total_entries: int = Field(..., ge=0, description="Total number of entries")
    total_size_bytes: int = Field(..., ge=0, description="Total size in bytes")

    # Usage metrics
    hit_count: int = Field(..., ge=0, description="Total cache hits")
    miss_count: int = Field(..., ge=0, description="Total cache misses")
    hit_rate: float = Field(..., ge=0, le=1, description="Cache hit rate")

    # Operation counts
    get_count: int = Field(default=0, ge=0, description="Number of get operations")
    set_count: int = Field(default=0, ge=0, description="Number of set operations")
    delete_count: int = Field(default=0, ge=0, description="Number of delete operations")

    # Performance metrics
    avg_get_time_ms: float = Field(default=0, ge=0, description="Average get time in ms")
    avg_set_time_ms: float = Field(default=0, ge=0, description="Average set time in ms")

    # Eviction stats
    eviction_count: int = Field(default=0, ge=0, description="Number of evictions")
    expired_count: int = Field(default=0, ge=0, description="Number of expired entries")

    # Memory usage
    memory_usage_mb: float = Field(..., ge=0, description="Memory usage in MB")
    memory_limit_mb: float = Field(..., ge=0, description="Memory limit in MB")
    memory_usage_percent: float = Field(..., ge=0, le=100, description="Memory usage percentage")

    # Timestamp
    collected_at: datetime = Field(default_factory=datetime.now, description="Stats collection time")

    @validator("hit_rate", always=True)
    def calculate_hit_rate(cls, v, values):
        """Calculate hit rate from hits and misses"""
        hits = values.get("hit_count", 0)
        misses = values.get("miss_count", 0)
        total = hits + misses
        if total > 0:
            return hits / total
        return 0.0

    class Config:
        use_enum_values = True


class CacheBatch(BaseModel):
    """Batch cache operations"""
    operations: List[CacheOperation] = Field(..., description="Batch operations")

    # Batch options
    atomic: bool = Field(default=False, description="Execute as atomic transaction")
    parallel: bool = Field(default=False, description="Execute in parallel")
    stop_on_error: bool = Field(default=False, description="Stop on first error")

    # Performance options
    batch_size: int = Field(default=100, ge=1, le=10000, description="Batch size for processing")
    timeout_seconds: Optional[float] = Field(default=None, description="Batch operation timeout")

    @validator("operations")
    def validate_operations(cls, v):
        """Validate operations list is not empty"""
        if not v:
            raise ValueError("Operations list cannot be empty")
        return v

    class Config:
        validate_assignment = True


class CacheResult(BaseModel):
    """Result from cache operation"""
    success: bool = Field(..., description="Operation success status")
    operation: str = Field(..., description="Operation performed")

    # Result data
    value: Optional[Any] = Field(default=None, description="Retrieved value for get operation")
    values: Optional[Dict[str, Any]] = Field(default=None, description="Multiple values for batch get")

    # Operation info
    key: Optional[str] = Field(default=None, description="Cache key")
    keys_affected: int = Field(default=0, ge=0, description="Number of keys affected")

    # Performance
    duration_ms: float = Field(default=0, ge=0, description="Operation duration in ms")
    from_cache: bool = Field(default=True, description="Whether value was from cache")

    # Error info
    error: Optional[str] = Field(default=None, description="Error message if failed")

    class Config:
        validate_assignment = True