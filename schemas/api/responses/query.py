"""
Query response schemas
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class QuerySource(BaseModel):
    """Source information for query response"""
    rank: int = Field(..., description="Ranking position")
    score: float = Field(..., description="Relevance score")
    document_id: str = Field(..., description="Document identifier")
    document_name: str = Field(..., description="Document file name")
    document_title: str = Field(..., description="Document title")
    document_url: str = Field(..., description="Document URL in MinIO")
    page_number: int = Field(..., description="Page number in the document")
    text_preview: str = Field(..., description="Preview of relevant text chunk")
    created_at: int = Field(default=0, description="Creation timestamp")


class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    answer: str = Field(..., description="Generated answer")
    sources: List[QuerySource] = Field(..., description="Source documents used")
    processing_time: float = Field(..., description="Processing time in seconds")
    model_used: str = Field(..., description="LLM model used for generation")
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    remaining_credits: int = Field(default=0, description="User's remaining credits")

    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "RAG stands for Retrieval-Augmented Generation...",
                "sources": [
                    {
                        "document_id": "doc_123",
                        "document_title": "RAG Overview",
                        "page_number": 1,
                        "chunk_text": "Retrieval-Augmented Generation (RAG) is...",
                        "score": 0.95
                    }
                ],
                "processing_time": 1.23,
                "model_used": "gpt-4o-mini"
            }
        }
    }
