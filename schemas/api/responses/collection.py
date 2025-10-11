"""
Collection management response schemas
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
from schemas.api.requests.query import QueryOptions


class CollectionInfo(BaseModel):
    """Information about a collection"""
    name: str = Field(..., description="Collection name")
    scope: str = Field(..., description="Collection scope (private/shared)")
    description: Optional[str] = Field(None, description="Collection description")
    document_count: int = Field(0, description="Number of documents in collection")
    chunk_count: int = Field(0, description="Number of chunks in collection")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    created_by: str = Field(..., description="User ID who created the collection")
    created_by_email: Optional[str] = Field(None, description="Email of the creator")
    updated_at: Optional[str] = Field(None, description="Last update timestamp (ISO format)")
    size_bytes: int = Field(0, description="Total storage size in bytes")
    size_mb: float = Field(0.0, description="Total storage size in megabytes")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")

    # Collection technical info
    milvus_collection_name: str = Field(..., description="Milvus collection name")
    minio_prefix: str = Field(..., description="MinIO storage prefix")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "legal-research",
                    "scope": "private",
                    "description": "Legal research documents",
                    "document_count": 15,
                    "chunk_count": 320,
                    "created_at": "2025-10-09T10:30:00Z",
                    "created_by": "17d0faab-0830-4007-8ed6-73cfd049505b",
                    "created_by_email": "user@example.com",
                    "updated_at": "2025-10-09T14:20:00Z",
                    "size_bytes": 5242880,
                    "size_mb": 5.0,
                    "metadata": {"category": "legal"},
                    "milvus_collection_name": "17d0faab_0830_4007_8ed6_73cfd049505b_col_legal_research_chunks_1536",
                    "minio_prefix": "users/17d0faab-0830-4007-8ed6-73cfd049505b/collections/legal-research/docs/"
                }
            ]
        }
    }


class CreateCollectionResponse(BaseModel):
    """Response after creating a collection"""
    message: str = Field(..., description="Success message")
    collection: CollectionInfo = Field(..., description="Created collection information")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Collection 'legal-research' created successfully",
                    "collection": {
                        "name": "legal-research",
                        "scope": "private",
                        "description": "Legal research documents",
                        "document_count": 0,
                        "chunk_count": 0,
                        "created_at": "2025-10-09T10:30:00Z",
                        "created_by": "17d0faab-0830-4007-8ed6-73cfd049505b",
                        "created_by_email": "user@example.com",
                        "updated_at": None,
                        "size_bytes": 0,
                        "size_mb": 0.0,
                        "milvus_collection_name": "17d0faab_0830_4007_8ed6_73cfd049505b_col_legal_research_chunks_1536",
                        "minio_prefix": "users/17d0faab-0830-4007-8ed6-73cfd049505b/collections/legal-research/docs/"
                    }
                }
            ]
        }
    }


class ListCollectionsResponse(BaseModel):
    """Response for listing collections"""
    total_count: int = Field(..., description="Total number of collections")
    collections: List[CollectionInfo] = Field(..., description="List of collections")
    scope_filter: Optional[str] = Field(None, description="Applied scope filter")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_count": 2,
                    "collections": [
                        {
                            "name": "legal-research",
                            "scope": "private",
                            "document_count": 15,
                            "chunk_count": 320,
                            "created_at": "2025-10-09T10:30:00Z",
                            "created_by": "17d0faab-0830-4007-8ed6-73cfd049505b",
                            "created_by_email": "user@example.com",
                            "updated_at": "2025-10-09T14:20:00Z",
                            "size_bytes": 5242880,
                            "size_mb": 5.0,
                            "milvus_collection_name": "17d0faab_col_legal_research_chunks_1536",
                            "minio_prefix": "users/17d0faab/collections/legal-research/docs/"
                        }
                    ],
                    "scope_filter": "private"
                }
            ]
        }
    }


class DeleteCollectionResponse(BaseModel):
    """Response after deleting a collection"""
    message: str = Field(..., description="Success message")
    collection_name: str = Field(..., description="Deleted collection name")
    scope: str = Field(..., description="Collection scope")
    documents_deleted: int = Field(0, description="Number of documents deleted")
    chunks_deleted: int = Field(0, description="Number of chunks deleted")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Collection 'legal-research' deleted successfully",
                    "collection_name": "legal-research",
                    "scope": "private",
                    "documents_deleted": 15,
                    "chunks_deleted": 320
                }
            ]
        }
    }


class CollectionStatsResponse(BaseModel):
    """Detailed collection statistics"""
    collection: CollectionInfo = Field(..., description="Collection information")
    statistics: Dict[str, Any] = Field(..., description="Detailed statistics")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "collection": {
                        "name": "legal-research",
                        "scope": "private",
                        "document_count": 15,
                        "chunk_count": 320,
                        "created_at": "2025-10-09T10:30:00Z",
                        "created_by": "17d0faab-0830-4007-8ed6-73cfd049505b",
                        "created_by_email": "user@example.com",
                        "updated_at": "2025-10-09T14:20:00Z",
                        "size_bytes": 5242880,
                        "size_mb": 5.0,
                        "milvus_collection_name": "17d0faab_col_legal_research_chunks_1536",
                        "minio_prefix": "users/17d0faab/collections/legal-research/docs/"
                    },
                    "statistics": {
                        "avg_chunks_per_document": 21.3,
                        "total_pages": 450,
                        "last_ingested": "2025-10-09T14:20:00Z",
                        "embedding_model": "text-embedding-3-small"
                    }
                }
            ]
        }
    }


class CollectionSearchResult(BaseModel):
    """Single search result from collection query"""
    score: float = Field(..., description="Relevance score (0-1, cosine similarity)")
    document_id: str = Field(..., description="Document identifier")
    text: str = Field(..., description="Chunk text content")
    source_type: str = Field(..., description="Source type (private/shared)")
    chunk_index: int = Field(0, description="Chunk index in document")
    page_number: int = Field(0, description="Page number in document")
    document_title: str = Field("Unknown", description="Document title")
    collection_name: str = Field(..., description="Collection name where result was found")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CollectionQueryResponse(BaseModel):
    """Response from collection query endpoint"""
    results: List[CollectionSearchResult] = Field(
        ...,
        description="Search results from all queried collections"
    )
    generated_answer: Optional[str] = Field(
        None,
        description="Generated answer based on retrieved results"
    )
    success: bool = Field(..., description="Whether the query succeeded")
    processing_time: float = Field(..., description="Processing time in seconds")
    collections_searched: int = Field(..., description="Number of collections searched")
    total_results: int = Field(..., description="Total number of results found")
    options_used: Optional[QueryOptions] = Field(
        None,
        description="Query options that were applied (tone, lang, citations)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {
                            "score": 0.89,
                            "document_id": "doc_abc123",
                            "text": "Sözleşme fesih koşulları...",
                            "source_type": "private",
                            "chunk_index": 5,
                            "page_number": 12,
                            "document_title": "İş Sözleşmesi Örneği",
                            "collection_name": "sozlesmeler",
                            "metadata": {"created_at": "2025-01-10"}
                        }
                    ],
                    "generated_answer": "Collection belgelerinize göre, sözleşme fesih koşulları şunlardır: ...",
                    "success": True,
                    "processing_time": 1.25,
                    "collections_searched": 2,
                    "total_results": 5,
                    "options_used": {
                        "tone": "resmi",
                        "lang": "tr",
                        "citations": True,
                        "stream": False
                    }
                }
            ]
        }
    }
