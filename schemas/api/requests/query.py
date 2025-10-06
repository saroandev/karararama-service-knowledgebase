"""
Query request schemas
"""
from pydantic import BaseModel, Field
from schemas.api.requests.scope import DataScope


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    question: str = Field(..., description="Question to ask")

    # Multi-tenant scope parameter
    search_scope: DataScope = Field(
        default=DataScope.ALL,
        description="Data scope to search: PRIVATE (only user's data), SHARED (only org shared), or ALL (both)"
    )

    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of sources to retrieve from vector DB")
    use_reranker: bool = Field(default=True, description="Whether to use reranking for better results")

    # Source filtering parameters
    min_relevance_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score (0-1) for sources to be included. Higher = more strict filtering."
    )
    include_low_confidence_sources: bool = Field(
        default=False,
        description="If true, includes low-confidence sources separately in the response"
    )
    max_sources_in_context: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of high-confidence sources to include in LLM context"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What is RAG?",
                "search_scope": "all",
                "top_k": 5,
                "use_reranker": True,
                "min_relevance_score": 0.7,
                "include_low_confidence_sources": False,
                "max_sources_in_context": 5
            }
        }
    }
