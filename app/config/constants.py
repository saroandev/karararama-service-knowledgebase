"""
Constants for the RAG system.

This module contains all constant values used throughout the application.
These values should not change during runtime.
"""

# Milvus Constants
MILVUS_DEFAULT_HOST = "localhost"
MILVUS_DEFAULT_PORT = 19530
# MILVUS_DEFAULT_COLLECTION removed - System now uses scope-based collections only
# Collections are automatically named based on scope and dimension
MILVUS_METRIC_TYPE = "COSINE"
MILVUS_INDEX_TYPE = "HNSW"
MILVUS_NLIST = 1024
MILVUS_NPROBE = 10
MILVUS_M = 8
MILVUS_EF_CONSTRUCTION = 64

# MinIO Constants
MINIO_DEFAULT_ENDPOINT = "localhost:9000"
MINIO_DEFAULT_ACCESS_KEY = "minioadmin"
MINIO_DEFAULT_SECRET_KEY = "minioadmin"
MINIO_DEFAULT_BUCKET_DOCS = "raw-documents"
MINIO_DEFAULT_BUCKET_CHUNKS = "rag-chunks"

# Embedding Constants
EMBEDDING_OPENAI_MODEL = "text-embedding-3-small"
EMBEDDING_OPENAI_DIMENSION = 1536
EMBEDDING_LOCAL_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_LOCAL_DIMENSION = 384
EMBEDDING_DEFAULT_BATCH_SIZE = 32
EMBEDDING_MAX_BATCH_SIZE = 100

# LLM Constants
LLM_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
LLM_OLLAMA_DEFAULT_MODEL = "qwen2.5:7b-instruct"
LLM_MAX_TOKENS = 500
LLM_TEMPERATURE = 0.7
LLM_TOP_P = 0.9

# Chunking Constants
CHUNK_SIZE_MIN = 100
CHUNK_SIZE_MAX = 1000
CHUNK_SIZE_DEFAULT = 512
CHUNK_OVERLAP_MIN = 0
CHUNK_OVERLAP_MAX = 200
CHUNK_OVERLAP_DEFAULT = 50
CHUNKING_METHODS = ["token", "semantic", "document", "hybrid"]
CHUNKING_DEFAULT_METHOD = "token"

# Semantic Chunking Constants
SEMANTIC_SIMILARITY_MIN = 0.0
SEMANTIC_SIMILARITY_MAX = 1.0
SEMANTIC_SIMILARITY_DEFAULT = 0.7

# Query Constants
QUERY_DEFAULT_TOP_K = 5
QUERY_MAX_TOP_K = 20
QUERY_MIN_TOP_K = 1
QUERY_SCORE_THRESHOLD = 0.7

# File Processing Constants
SUPPORTED_FILE_TYPES = [".pdf"]
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# System Constants
DEFAULT_ENCODING = "utf-8"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

# API Constants
API_VERSION = "1.0.0"
API_TITLE = "onedocs-service-knowledgebase"
API_DESCRIPTION = "OneDocs Knowledge Base Service - Multi-tenant RAG system with vector search"
API_DEFAULT_HOST = "0.0.0.0"
API_DEFAULT_PORT = 8080

# Timeout Constants (in seconds)
TIMEOUT_MILVUS_CONNECTION = 30
TIMEOUT_MINIO_CONNECTION = 30
TIMEOUT_EMBEDDING_GENERATION = 60
TIMEOUT_LLM_GENERATION = 120
TIMEOUT_PDF_PARSING = 60

# Retry Constants
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_MAX_DELAY = 30

# Cache Constants
CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_MAX_SIZE = 1000

# Error Messages
ERROR_INVALID_FILE_TYPE = "Invalid file type. Only PDF files are supported."
ERROR_FILE_TOO_LARGE = f"File size exceeds maximum limit of {MAX_FILE_SIZE_MB}MB"
ERROR_MILVUS_CONNECTION = "Failed to connect to Milvus database"
ERROR_MINIO_CONNECTION = "Failed to connect to MinIO storage"
ERROR_EMBEDDING_GENERATION = "Failed to generate embeddings"
ERROR_LLM_GENERATION = "Failed to generate response"
ERROR_PDF_PARSING = "Failed to parse PDF document"
ERROR_DOCUMENT_NOT_FOUND = "Document not found"
ERROR_CHUNK_NOT_FOUND = "Chunk not found"

# Success Messages
SUCCESS_DOCUMENT_INGESTED = "Document successfully ingested"
SUCCESS_DOCUMENT_DELETED = "Document successfully deleted"
SUCCESS_QUERY_COMPLETED = "Query completed successfully"

# Service Type Constants (Usage Tracking)
class ServiceType:
    """
    Service types for usage tracking in auth service

    These constants are used when reporting usage to the auth service
    via the consume_usage() endpoint.
    """
    QUERY = "rag_query"
    INGEST = "rag_ingest"
    INGEST_COLLECTION = "rag_ingest_collection"
    LIST_DOCUMENTS = "rag_list_documents"
    DELETE_DOCUMENT = "rag_delete"

    # All valid service types
    ALL = [QUERY, INGEST, INGEST_COLLECTION, LIST_DOCUMENTS, DELETE_DOCUMENT]