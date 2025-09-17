"""
Milvus configuration schema
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal


class MilvusSettings(BaseModel):
    """Milvus vector database configuration"""

    host: str = Field(default="localhost", description="Milvus server host")
    port: int = Field(default=19530, description="Milvus server port")
    collection_name: str = Field(default="rag_chunks", description="Collection name")

    # Collection settings
    dimension: int = Field(default=1536, description="Vector dimension")
    metric_type: Literal["L2", "IP", "COSINE"] = Field(
        default="COSINE",
        description="Distance metric type"
    )

    # Index settings
    index_type: Literal["HNSW", "IVF_FLAT", "IVF_SQ8", "FLAT"] = Field(
        default="HNSW",
        description="Index type for vector search"
    )
    index_params: dict = Field(
        default={"M": 8, "efConstruction": 64},
        description="Index parameters"
    )

    # Search settings
    search_params: dict = Field(
        default={"metric_type": "COSINE", "ef": 64},
        description="Search parameters"
    )

    # Connection settings
    timeout: float = Field(default=30.0, description="Connection timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum connection retries")
    retry_delay: float = Field(default=1.0, description="Delay between retries in seconds")

    # Performance settings
    batch_size: int = Field(default=100, description="Batch size for bulk operations")
    consistency_level: Literal["Strong", "Session", "Bounded", "Eventually", "Customized"] = Field(
        default="Session",
        description="Consistency level"
    )

    class Config:
        validate_assignment = True
        use_enum_values = True