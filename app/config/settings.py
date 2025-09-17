import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET_DOCS = os.getenv("MINIO_BUCKET_DOCS", "raw-documents")
    MINIO_BUCKET_CHUNKS = os.getenv("MINIO_BUCKET_CHUNKS", "rag-chunks")

    MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "rag_chunks")

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

settings = Settings()