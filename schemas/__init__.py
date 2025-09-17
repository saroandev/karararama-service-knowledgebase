"""
Schemas package for OneDocs RAG system.
Central location for all data models and schemas.
"""

# API schemas (existing - for backward compatibility)
from schemas.api.requests.query import QueryRequest
from schemas.api.requests.ingest import IngestRequest

from schemas.api.responses.query import QueryResponse
from schemas.api.responses.ingest import (
    BaseIngestResponse,
    SuccessfulIngestResponse,
    ExistingDocumentResponse,
    FailedIngestResponse,
    BatchIngestResponse,
    FileIngestStatus
)
from schemas.api.responses.document import DocumentInfo
from schemas.api.responses.health import HealthResponse

# Internal schemas
from schemas.internal.chunk import SimpleChunk, ChunkMetadata

# Parsing schemas
from schemas.parsing.document import DocumentMetadata, DocumentProcessingResult
from schemas.parsing.page import PageContent

# Config schemas
from schemas.config.app import ApplicationConfig
from schemas.config.milvus import MilvusSettings
from schemas.config.minio import MinIOSettings
from schemas.config.llm import LLMSettings

# Chunking schemas
from schemas.chunking.base import (
    Chunk,
    ChunkMetadata as ChunkingMetadata,
    ChunkingConfig,
    ChunkingResult
)
from schemas.chunking.text import TextChunkConfig, TextChunkResult
from schemas.chunking.semantic import SemanticChunkConfig, SemanticChunkResult
from schemas.chunking.document import DocumentChunkConfig, DocumentElement
from schemas.chunking.hybrid import HybridChunkConfig, HybridChunkResult

# Storage schemas
from schemas.storage.minio import (
    BucketInfo,
    DocumentStorage,
    ChunkStorage as MinioChunkStorage,
    StorageRequest,
    StorageResponse
)
from schemas.storage.milvus import (
    CollectionSchema,
    FieldSchema as MilvusFieldSchema,
    VectorData,
    SearchRequest,
    SearchResult
)
from schemas.storage.cache import CacheEntry, CacheConfig, CacheStats

# Embeddings schemas
from schemas.embeddings.base import (
    EmbeddingProvider,
    EmbeddingConfig,
    EmbeddingRequest,
    EmbeddingResult
)
from schemas.embeddings.openai import OpenAIEmbeddingConfig, OpenAIEmbeddingResponse
from schemas.embeddings.local import LocalEmbeddingConfig, LocalModelInfo

# Retrieval schemas
from schemas.retrieval.search import (
    SearchQuery,
    SearchResult as RetrievalSearchResult,
    SearchResponse,
    SearchMetrics
)
from schemas.retrieval.reranker import (
    RerankerConfig,
    RerankerRequest,
    RerankerResponse,
    RerankingStrategy
)
from schemas.retrieval.hybrid import (
    HybridSearchConfig,
    HybridSearchQuery,
    HybridSearchResult
)

# Generation schemas
from schemas.generation.llm import (
    LLMProvider,
    LLMConfig,
    GenerationRequest,
    GenerationResponse,
    ChatMessage
)
from schemas.generation.prompt import (
    PromptTemplate,
    FewShotPrompt,
    ChainOfThoughtPrompt,
    PromptLibrary
)

# Pipeline schemas
from schemas.pipelines.ingest import (
    IngestPipelineConfig,
    IngestPipelineResult,
    IngestStage,
    BatchIngestRequest as PipelineBatchIngestRequest
)
from schemas.pipelines.query import (
    QueryPipelineConfig,
    QueryPipelineResult,
    QueryMode,
    StreamingQueryResult
)

# Indexing schemas
from schemas.indexing.milvus import (
    IndexType,
    MetricType,
    IndexConfig,
    IndexStatus,
    IndexingRequest,
    IndexingResult,
    CollectionStats
)

__all__ = [
    # API schemas (existing)
    "QueryRequest",
    "IngestRequest",
    "QueryResponse",
    "BaseIngestResponse",
    "SuccessfulIngestResponse",
    "ExistingDocumentResponse",
    "FailedIngestResponse",
    "BatchIngestResponse",
    "FileIngestStatus",
    "DocumentInfo",
    "HealthResponse",
    # Internal schemas
    "SimpleChunk",
    "ChunkMetadata",
    # Parsing schemas
    "DocumentMetadata",
    "DocumentProcessingResult",
    "PageContent",
    # Config schemas
    "ApplicationConfig",
    "MilvusSettings",
    "MinIOSettings",
    "LLMSettings",
    # Chunking schemas
    "Chunk",
    "ChunkingMetadata",
    "ChunkingConfig",
    "ChunkingResult",
    "TextChunkConfig",
    "TextChunkResult",
    "SemanticChunkConfig",
    "SemanticChunkResult",
    "DocumentChunkConfig",
    "DocumentElement",
    "HybridChunkConfig",
    "HybridChunkResult",
    # Storage schemas
    "BucketInfo",
    "DocumentStorage",
    "MinioChunkStorage",
    "StorageRequest",
    "StorageResponse",
    "CollectionSchema",
    "MilvusFieldSchema",
    "VectorData",
    "SearchRequest",
    "SearchResult",
    "CacheEntry",
    "CacheConfig",
    "CacheStats",
    # Embeddings schemas
    "EmbeddingProvider",
    "EmbeddingConfig",
    "EmbeddingRequest",
    "EmbeddingResult",
    "OpenAIEmbeddingConfig",
    "OpenAIEmbeddingResponse",
    "LocalEmbeddingConfig",
    "LocalModelInfo",
    # Retrieval schemas
    "SearchQuery",
    "RetrievalSearchResult",
    "SearchResponse",
    "SearchMetrics",
    "RerankerConfig",
    "RerankerRequest",
    "RerankerResponse",
    "RerankingStrategy",
    "HybridSearchConfig",
    "HybridSearchQuery",
    "HybridSearchResult",
    # Generation schemas
    "LLMProvider",
    "LLMConfig",
    "GenerationRequest",
    "GenerationResponse",
    "ChatMessage",
    "PromptTemplate",
    "FewShotPrompt",
    "ChainOfThoughtPrompt",
    "PromptLibrary",
    # Pipeline schemas
    "IngestPipelineConfig",
    "IngestPipelineResult",
    "IngestStage",
    "PipelineBatchIngestRequest",
    "QueryPipelineConfig",
    "QueryPipelineResult",
    "QueryMode",
    "StreamingQueryResult",
    # Indexing schemas
    "IndexType",
    "MetricType",
    "IndexConfig",
    "IndexStatus",
    "IndexingRequest",
    "IndexingResult",
    "CollectionStats",
]