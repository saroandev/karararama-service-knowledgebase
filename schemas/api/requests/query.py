"""
Query request schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from schemas.api.requests.scope import DataScope


class QueryOptions(BaseModel):
    """Query behavior options for controlling LLM response generation"""

    tone: str = Field(
        default="resmi",
        description="LLM response tone: resmi (formal), samimi (friendly), teknik (technical), basit (simple)"
    )

    lang: str = Field(
        default="tr",
        description="Response language code: tr (Turkish), en (English)"
    )

    citations: bool = Field(
        default=True,
        description="Include source citations in format [Kaynak 1], [Kaynak 2]"
    )

    stream: bool = Field(
        default=False,
        description="Enable streaming response (SSE) - future feature"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "tone": "resmi",
                "lang": "tr",
                "citations": True,
                "stream": False
            }
        }
    }


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    question: str = Field(..., description="Question to ask")

    # Multi-source selection parameter
    sources: List[DataScope] = Field(
        default=[DataScope.PRIVATE, DataScope.SHARED],
        description="List of data sources to search: 'private' (your documents), 'shared' (organization documents), 'mevzuat' (legislation), 'karar' (court decisions)"
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

    # Query behavior options
    options: Optional[QueryOptions] = Field(
        default=None,
        description="Query behavior options (tone, language, citations, streaming)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "İcra ve İflas Kanunu nedir?",
                "sources": ["private", "mevzuat"],
                "top_k": 5,
                "use_reranker": True,
                "min_relevance_score": 0.7,
                "include_low_confidence_sources": False,
                "max_sources_in_context": 5,
                "options": {
                    "tone": "resmi",
                    "lang": "tr",
                    "citations": True,
                    "stream": False
                }
            }
        }
    }
