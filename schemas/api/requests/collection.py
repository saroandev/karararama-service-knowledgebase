"""
Collection management request schemas
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from schemas.api.requests.scope import IngestScope


class CreateCollectionRequest(BaseModel):
    """Request schema for creating a new collection"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Collection name (alphanumeric, hyphens, underscores only)"
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
        """Validate collection name format"""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                "Collection name must contain only alphanumeric characters, hyphens, and underscores"
            )
        # Reserved names
        if v.lower() in ['default', 'admin', 'system', 'shared', 'private']:
            raise ValueError(f"'{v}' is a reserved name and cannot be used")
        return v.lower()  # Normalize to lowercase

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
