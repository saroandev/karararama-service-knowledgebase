"""
Query response schemas
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class QuerySource(BaseModel):
    """Unified source citation format (matches external sources)"""
    document_id: str = Field(..., description="Document identifier")
    chunk_index: Optional[int] = Field(None, description="Chunk index in document")
    text: str = Field(..., description="Full chunk text content")
    relevance_score: float = Field(..., description="Relevance score (0-1)")
    document_url: str = Field(..., description="Presigned document download URL")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata (filename, title, source/collection_name, bucket, page_number, etc.)"
    )


class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    answer: str = Field(..., description="Generated answer")
    role: str = Field(default="assistant", description="Message role (always 'assistant' for responses)")
    conversation_id: str = Field(..., description="Conversation ID for maintaining chat history")
    citations: List[QuerySource] = Field(..., description="High-confidence source citations used for the answer")
    processing_time: float = Field(..., description="Processing time in seconds")
    model_used: str = Field(..., description="LLM model used for generation")
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    remaining_credits: int = Field(default=0, description="User's remaining credits")

    # Filtering metadata
    total_sources_retrieved: int = Field(default=0, description="Total sources retrieved from vector DB")
    sources_after_filtering: int = Field(default=0, description="Sources remaining after relevance filtering")
    min_score_applied: float = Field(default=0.0, description="Minimum relevance score threshold applied")
    low_confidence_citations: Optional[List[QuerySource]] = Field(
        default=None,
        description="Citations below the relevance threshold (only if include_low_confidence_sources=true)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "RAG stands for Retrieval-Augmented Generation...",
                "role": "assistant",
                "conversation_id": "conv-123e4567-e89b-12d3-a456-426614174000",
                "citations": [
                    {
                        "document_id": "doc_123",
                        "chunk_index": 3,
                        "text": "Retrieval-Augmented Generation (RAG) is...",
                        "relevance_score": 0.95,
                        "document_url": "http://localhost:9000/org-abc/users/xyz/docs/doc-123/file.pdf?X-Amz-...",
                        "metadata": {
                            "filename": "RAG Overview.pdf",
                            "title": "RAG Overview",
                            "bucket": "org-abc123",
                            "scope": "private",
                            "page_number": 1,
                            "collection_name": "research-papers"
                        }
                    }
                ],
                "processing_time": 1.23,
                "model_used": "gpt-4o-mini",
                "tokens_used": 150,
                "remaining_credits": 9850
            }
        }
    }
