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
    # PUBLIC = "public"      # Public data (if applicable)


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
        - PRIVATE: user_{user_id}_chunks_{dimension}
        - SHARED: org_{org_id}_shared_chunks_{dimension}

        Note: UUID dashes are converted to underscores for Milvus compatibility
        (Milvus only allows letters, numbers, and underscores)

        Args:
            dimension: Embedding dimension (default: 1536 for OpenAI)

        Returns:
            Collection name string (safe for Milvus)
        """
        if self.scope_type == DataScope.PRIVATE:
            # User ID is globally unique, no need for org_id prefix
            safe_user_id = self.user_id.replace('-', '_')
            return f"user_{safe_user_id}_chunks_{dimension}"
        elif self.scope_type == DataScope.SHARED:
            # Organization shared collection needs org_id
            safe_org_id = self.organization_id.replace('-', '_')
            return f"org_{safe_org_id}_shared_chunks_{dimension}"
        else:
            raise ValueError(f"Cannot generate collection name for scope type: {self.scope_type}")

    def get_bucket_name(self) -> str:
        """
        Generate MinIO bucket name for the organization

        New structure: One bucket per organization with folder-based isolation
        Format: org-{org_id}

        Returns:
            Bucket name string (lowercase, hyphens)
        """
        return f"org-{self.organization_id}".lower()

    def get_object_prefix(self, category: str = "docs") -> str:
        """
        Generate MinIO object prefix (folder path) for this scope

        Simplified folder structure to avoid deep nesting:
        - PRIVATE: {user_id}/{category}/
        - SHARED: shared/{category}/

        Args:
            category: Storage category ("docs" or "chunks")

        Returns:
            Object prefix string (folder path with trailing slash)

        Examples:
            Private docs: "17d0faab-0830-4007-8ed6-73cfd049505b/docs/"
            Shared chunks: "shared/chunks/"
        """
        if self.scope_type == DataScope.PRIVATE:
            return f"{self.user_id}/{category}/"
        elif self.scope_type == DataScope.SHARED:
            return f"shared/{category}/"
        else:
            raise ValueError(f"Cannot generate object prefix for scope type: {self.scope_type}")

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
