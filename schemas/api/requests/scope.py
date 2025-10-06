"""
Data scope models for multi-tenant isolation
"""
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class DataScope(str, Enum):
    """Data scope types for multi-tenant architecture"""
    PRIVATE = "private"      # User's private data only
    SHARED = "shared"        # Organization shared data
    ALL = "all"              # All accessible scopes (for queries)


class ScopeIdentifier(BaseModel):
    """
    Identifies a specific data scope in the multi-tenant system

    This model is used to generate collection names and bucket names
    based on organization, user, and scope type.
    """
    organization_id: str = Field(..., description="Organization ID")
    scope_type: DataScope = Field(..., description="Type of data scope")
    user_id: Optional[str] = Field(None, description="User ID (required for PRIVATE scope)")

    @field_validator('user_id')
    @classmethod
    def validate_user_id_for_private(cls, v, info):
        """Validate that user_id is provided for PRIVATE scope"""
        scope_type = info.data.get('scope_type')
        if scope_type == DataScope.PRIVATE and not v:
            raise ValueError("user_id is required for PRIVATE scope")
        return v

    def get_collection_name(self, dimension: int = 1536) -> str:
        """
        Generate Milvus collection name for this scope

        Format:
        - PRIVATE: org_{org_id}_user_{user_id}_private_chunks_{dimension}
        - SHARED: org_{org_id}_shared_chunks_{dimension}

        Args:
            dimension: Embedding dimension (default: 1536 for OpenAI)

        Returns:
            Collection name string
        """
        if self.scope_type == DataScope.PRIVATE:
            return f"org_{self.organization_id}_user_{self.user_id}_private_chunks_{dimension}"
        elif self.scope_type == DataScope.SHARED:
            return f"org_{self.organization_id}_shared_chunks_{dimension}"
        else:
            raise ValueError(f"Cannot generate collection name for scope type: {self.scope_type}")

    def get_bucket_name(self, category: str = "docs") -> str:
        """
        Generate MinIO bucket name for this scope

        Format:
        - PRIVATE docs: org-{org_id}-user-{user_id}-docs
        - PRIVATE chunks: org-{org_id}-user-{user_id}-chunks
        - SHARED docs: org-{org_id}-shared-docs
        - SHARED chunks: org-{org_id}-shared-chunks

        Args:
            category: Bucket category ("docs" or "chunks")

        Returns:
            Bucket name string (lowercase, hyphens)
        """
        if self.scope_type == DataScope.PRIVATE:
            return f"org-{self.organization_id}-user-{self.user_id}-{category}".lower()
        elif self.scope_type == DataScope.SHARED:
            return f"org-{self.organization_id}-shared-{category}".lower()
        else:
            raise ValueError(f"Cannot generate bucket name for scope type: {self.scope_type}")

    def __str__(self) -> str:
        """String representation"""
        if self.scope_type == DataScope.PRIVATE:
            return f"ScopeIdentifier(org={self.organization_id}, user={self.user_id}, scope=PRIVATE)"
        elif self.scope_type == DataScope.SHARED:
            return f"ScopeIdentifier(org={self.organization_id}, scope=SHARED)"
        return f"ScopeIdentifier(scope={self.scope_type})"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "organization_id": "org_123",
                    "scope_type": "private",
                    "user_id": "user_456"
                },
                {
                    "organization_id": "org_123",
                    "scope_type": "shared",
                    "user_id": None
                }
            ]
        }
    }
