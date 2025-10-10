"""
Collection management request schemas
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from schemas.api.requests.scope import IngestScope
from schemas.api.requests.query import CollectionFilter, QueryOptions


class CreateCollectionRequest(BaseModel):
    """Request schema for creating a new collection"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Collection name (supports Turkish characters, spaces, and special characters)"
    )
    scope: IngestScope = Field(
        ...,
        description="Collection scope: 'private' or 'shared'"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional collection description"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional custom metadata"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """
        Validate collection name format

        Accepts:
        - Unicode letters (including Turkish: ş, ğ, ı, ö, ü, ç)
        - Numbers
        - Spaces
        - Common special characters: - _ . , ( ) [ ]
        """
        import re

        # Strip leading/trailing whitespace
        v = v.strip()

        # Check if empty after stripping
        if not v:
            raise ValueError("Collection name cannot be empty")

        # Allow Unicode letters, numbers, spaces, and common special characters
        # \w includes [a-zA-Z0-9_] plus Unicode letters
        if not re.match(r'^[\w\s\-.,()[\]]+$', v, re.UNICODE):
            raise ValueError(
                "Collection name can contain letters (including Turkish), numbers, spaces, "
                "and these special characters: - _ . , ( ) [ ]"
            )

        # Reserved names (case-insensitive check)
        normalized_lower = v.lower()
        reserved = ['default', 'admin', 'system', 'shared', 'private', 'all']
        if normalized_lower in reserved:
            raise ValueError(f"'{v}' is a reserved name and cannot be used")

        return v  # Keep original case and format

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "legal-research",
                    "scope": "private",
                    "description": "Legal research documents and analysis"
                },
                {
                    "name": "contracts",
                    "scope": "shared",
                    "description": "Organization-wide contract repository",
                    "metadata": {
                        "department": "legal",
                        "retention_years": 7
                    }
                }
            ]
        }
    }


class UpdateCollectionRequest(BaseModel):
    """Request schema for updating a collection"""
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Updated description"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata (replaces existing)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated legal research collection",
                    "metadata": {"last_review": "2025-10-09"}
                }
            ]
        }
    }


class CollectionQueryRequest(BaseModel):
    """Request schema for querying collections"""
    question: str = Field(..., description="Question to search for in collections")
    collections: List[CollectionFilter] = Field(
        ...,
        description="List of collections to search with their scopes"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of results per collection")
    min_relevance_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score threshold"
    )
    options: Optional[QueryOptions] = Field(
        default=None,
        description="Query options for tone, language, citations"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "Sözleşme fesih koşulları nelerdir?",
                    "collections": [
                        {"name": "sozlesmeler", "scopes": ["private", "shared"]},
                        {"name": "kanunlar", "scopes": ["private"]}
                    ],
                    "top_k": 5,
                    "min_relevance_score": 0.7,
                    "options": {
                        "tone": "resmi",
                        "lang": "tr",
                        "citations": True
                    }
                }
            ]
        }
    }
