"""
Query request schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from schemas.api.requests.scope import DataScope


class CollectionFilter(BaseModel):
    """
    Collection filter with scope specification

    Allows fine-grained control over which collections to search in which scopes.
    Example: Search "sozlesmeler" collection only in private scope,
             but "kanunlar" collection in both private and shared scopes.
    """
    name: str = Field(..., description="Collection name (case-sensitive, Turkish characters supported)")
    scopes: List[DataScope] = Field(
        ...,
        description="Scopes to search this collection in. Only 'private' and 'shared' are allowed for collections."
    )

    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v):
        """Validate that scopes only contain PRIVATE or SHARED"""
        allowed_scopes = {DataScope.PRIVATE, DataScope.SHARED}
        for scope in v:
            if scope not in allowed_scopes:
                raise ValueError(
                    f"Collection scopes can only be 'private' or 'shared'. "
                    f"Got: '{scope.value}'. Use 'sources' parameter for external data sources like 'mevzuat' or 'karar'."
                )
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "sozlesmeler",
                    "scopes": ["private", "shared"]
                },
                {
                    "name": "kanunlar",
                    "scopes": ["private"]
                }
            ]
        }
    }


class QueryOptions(BaseModel):
    """Query behavior options for controlling LLM response generation"""

    tone: str = Field(
        default="resmi",
        description="LLM response tone: resmi (formal), samimi (friendly), teknik (technical), öğretici (instructive)"
    )

    lang: str = Field(
        default="tr",
        description="Response language code: tr (Turkish), eng (English)"
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
            "examples": [
                {
                    "tone": "resmi",
                    "lang": "tr",
                    "citations": True,
                    "stream": False
                },
                {
                    "tone": "resmi",
                    "lang": "eng",
                    "citations": True,
                    "stream": False
                }
            ]
        }
    }


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    question: str = Field(..., description="Question to ask")

    # Multi-source selection parameter
    sources: List[DataScope] = Field(
        default=[],
        description="List of data sources to search: 'private' (your documents), 'shared' (organization documents), 'mevzuat' (legislation), 'karar' (court decisions). If empty, no search is performed."
    )

    # Collection filtering (optional) - NEW: scope-aware collection filtering
    collections: Optional[List[CollectionFilter]] = Field(
        default=None,
        description=(
            "Optional collection filters with scope specification. "
            "If None, NO collections are searched (empty result for Milvus). "
            "Each filter specifies which collection to search in which scopes (private/shared). "
            "Example: [{'name': 'sozlesmeler', 'scopes': ['private', 'shared']}, {'name': 'kanunlar', 'scopes': ['private']}]"
        )
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
            "examples": [
                {
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
                },
                {
                    "question": "What are the key legal principles?",
                    "sources": ["private", "shared"],
                    "collections": [
                        {"name": "legal-research", "scopes": ["private", "shared"]},
                        {"name": "contracts", "scopes": ["private"]}
                    ],
                    "top_k": 5,
                    "use_reranker": True,
                    "options": {
                        "tone": "resmi",
                        "lang": "eng",
                        "citations": True
                    }
                }
            ]
        }
    }
