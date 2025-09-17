"""
Schemas package for OneDocs RAG system.
Central location for all data models and schemas.
"""

# Request schemas
from schemas.requests.query import QueryRequest
from schemas.requests.ingest import IngestRequest

# Response schemas
from schemas.responses.query import QueryResponse
from schemas.responses.ingest import (
    BaseIngestResponse,
    SuccessfulIngestResponse,
    ExistingDocumentResponse,
    FailedIngestResponse,
    BatchIngestResponse,
    FileIngestStatus
)
from schemas.responses.document import DocumentInfo
from schemas.responses.health import HealthResponse

# Internal schemas
from schemas.internal.chunk import SimpleChunk, ChunkMetadata
from schemas.internal.document import DocumentMetadata

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
    "DocumentMetadata",
]