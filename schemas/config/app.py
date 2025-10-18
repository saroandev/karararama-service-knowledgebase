"""
Application configuration schema using Pydantic
"""
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import Optional


class ApplicationConfig(BaseSettings):
    """Main application configuration"""

    # MinIO Configuration
    minio_endpoint: str = Field(default="localhost:9000", env="MINIO_ENDPOINT")
    minio_root_user: str = Field(default="minioadmin", env="MINIO_ROOT_USER")
    minio_root_password: str = Field(default="minioadmin", env="MINIO_ROOT_PASSWORD")
    minio_secure: bool = Field(default=False, env="MINIO_SECURE")
    minio_bucket_docs: str = Field(default="raw-documents", env="MINIO_BUCKET_DOCS")
    minio_bucket_chunks: str = Field(default="rag-chunks", env="MINIO_BUCKET_CHUNKS")

    # Milvus Configuration
    milvus_host: str = Field(default="localhost", env="MILVUS_HOST")
    milvus_port: int = Field(default=19530, env="MILVUS_PORT")
    # milvus_collection removed - System now uses scope-based collections only

    # Embedding Configuration
    embedding_provider: str = Field(default="openai", env="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=1536, env="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    use_reranker: bool = Field(default=False, env="USE_RERANKER")
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", env="RERANKER_MODEL")

    # LLM Configuration
    llm_provider: str = Field(default="ollama", env="LLM_PROVIDER")
    ollama_model: str = Field(default="qwen2.5:7b-instruct", env="OLLAMA_MODEL")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")

    # Chunking Configuration
    chunking_model: str = Field(default="BAAI/bge-m3", env="CHUNKING_MODEL")
    default_chunk_size: int = Field(default=512, env="DEFAULT_CHUNK_SIZE")
    default_chunk_overlap: int = Field(default=50, env="DEFAULT_CHUNK_OVERLAP")
    default_chunking_method: str = Field(default="token", env="DEFAULT_CHUNKING_METHOD")
    max_chunk_size: int = Field(default=1000, env="MAX_CHUNK_SIZE")
    min_chunk_size: int = Field(default=100, env="MIN_CHUNK_SIZE")
    semantic_similarity_threshold: float = Field(default=0.7, env="SEMANTIC_SIMILARITY_THRESHOLD")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment

    def model_post_init(self, __context) -> None:
        """Convert string booleans to actual booleans if needed"""
        if isinstance(self.minio_secure, str):
            self.minio_secure = self.minio_secure.lower() == "true"
        if isinstance(self.use_reranker, str):
            self.use_reranker = self.use_reranker.lower() == "true"