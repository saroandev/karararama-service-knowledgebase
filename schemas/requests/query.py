"""
Query request schemas
"""
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    question: str = Field(..., description="Question to ask")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of results to return")
    use_reranker: bool = Field(default=True, description="Whether to use reranking for better results")

    class Config:
        schema_extra = {
            "example": {
                "question": "What is RAG?",
                "top_k": 5,
                "use_reranker": True
            }
        }