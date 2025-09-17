"""
Schemas package for OneDocs RAG system.
Central location for all data models and schemas.
"""

# Request schemas
from schemas.api.requests.query import QueryRequest
from schemas.api.requests.ingest import IngestRequest

# Response schemas
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

__all__ = [
    # Request schemas
    "QueryRequest",
    "IngestRequest",
    # Response schemas
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
]