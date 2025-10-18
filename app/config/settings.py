import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
    MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET_DOCS = os.getenv("MINIO_BUCKET_DOCS", "raw-documents")
    MINIO_BUCKET_CHUNKS = os.getenv("MINIO_BUCKET_CHUNKS", "rag-chunks")

    MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
    # MILVUS_COLLECTION removed - System now uses scope-based collections only
    # Collections are automatically named based on: user_{user_id}_chunks_{dimension} or org_{org_id}_shared_chunks_{dimension}
    MILVUS_CONNECTION_TIMEOUT = float(os.getenv("MILVUS_CONNECTION_TIMEOUT", "3.0"))
    MILVUS_MAX_RETRY = int(os.getenv("MILVUS_MAX_RETRY", "1"))

    # Embedding Configuration - Using OpenAI by default
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
    EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    USE_RERANKER = os.getenv("USE_RERANKER", "false").lower() == "true"
    RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Chunking Configuration
    CHUNKING_MODEL = os.getenv("CHUNKING_MODEL", "BAAI/bge-m3")
    DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", "512"))
    DEFAULT_CHUNK_OVERLAP = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "50"))
    DEFAULT_CHUNKING_METHOD = os.getenv("DEFAULT_CHUNKING_METHOD", "token")
    MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "1000"))
    MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "100"))
    SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.7"))

    # Authentication Configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

    # Auth Service Configuration
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
    AUTH_SERVICE_TIMEOUT = int(os.getenv("AUTH_SERVICE_TIMEOUT", "5"))

    # Global DB Service Configuration (Public Data Source)
    GLOBAL_DB_SERVICE_URL = os.getenv("GLOBAL_DB_SERVICE_URL", "http://localhost:8070")
    GLOBAL_DB_SERVICE_TIMEOUT = int(os.getenv("GLOBAL_DB_SERVICE_TIMEOUT", "30"))
    GLOBAL_DB_DEFAULT_BUCKET = os.getenv("GLOBAL_DB_DEFAULT_BUCKET", "mevzuat")

    # Query Source Filtering Configuration
    DEFAULT_MIN_RELEVANCE_SCORE = float(os.getenv("DEFAULT_MIN_RELEVANCE_SCORE", "0.7"))
    ENABLE_SOURCE_FILTERING = os.getenv("ENABLE_SOURCE_FILTERING", "true").lower() == "true"
    DEFAULT_MAX_SOURCES_IN_CONTEXT = int(os.getenv("DEFAULT_MAX_SOURCES_IN_CONTEXT", "5"))

    # PostgreSQL Configuration
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "rag_database")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "raguser")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "ragpassword")

settings = Settings()