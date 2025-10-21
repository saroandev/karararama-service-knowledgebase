"""
Data scope models for multi-tenant isolation
"""
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class DataScope(str, Enum):
    """Data scope types for multi-tenant architecture (used for collections only)"""
    PRIVATE = "private"      # User's private data only
    SHARED = "shared"        # Organization shared data
    ALL = "all"              # All accessible scopes (private + shared)


class IngestScope(str, Enum):
    """Data scope types allowed for document ingestion"""
    PRIVATE = "private"      # User's private data only
    SHARED = "shared"        # Organization shared data


class ScopeIdentifier(BaseModel):
    """
    Identifies a specific data scope in the multi-tenant system

    This model is used to generate collection names and bucket names
    based on organization, user, and scope type.

    Collections feature:
    - collection_name=None: Default space (backward compatible)
    - collection_name="xyz": Named collection for organized data grouping
    """
    organization_id: str = Field(..., description="Organization ID")
    scope_type: DataScope = Field(..., description="Type of data scope")
    user_id: Optional[str] = Field(None, description="User ID (required for PRIVATE scope)")
    collection_name: Optional[str] = Field(None, description="Optional collection name for data organization")

    @field_validator('user_id')
    @classmethod
    def validate_user_id_for_private(cls, v, info):
        """Validate that user_id is provided for PRIVATE scope"""
        scope_type = info.data.get('scope_type')
        if scope_type == DataScope.PRIVATE and not v:
            raise ValueError("user_id is required for PRIVATE scope")
        return v

    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        """
        Sanitize collection name for Milvus compatibility

        Converts:
        - Turkish characters to ASCII equivalents (ş->s, ğ->g, etc.)
        - Spaces and special characters to underscores
        - Uppercase to lowercase
        - Multiple underscores to single

        Args:
            name: Original collection name (can contain Turkish chars, spaces, etc.)

        Returns:
            Milvus-safe collection name
        """
        # Turkish character mapping
        turkish_map = {
            'ş': 's', 'Ş': 's',
            'ğ': 'g', 'Ğ': 'g',
            'ı': 'i', 'İ': 'i',
            'ö': 'o', 'Ö': 'o',
            'ü': 'u', 'Ü': 'u',
            'ç': 'c', 'Ç': 'c'
        }

        # Convert Turkish characters
        sanitized = ''.join(turkish_map.get(c, c) for c in name)

        # Convert to lowercase
        sanitized = sanitized.lower()

        # Replace spaces and special characters with underscores
        # Keep only alphanumeric and underscores
        import re
        sanitized = re.sub(r'[^a-z0-9_]', '_', sanitized)

        # Replace multiple underscores with single
        sanitized = re.sub(r'_+', '_', sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')

        return sanitized

    def get_collection_name(self, dimension: int = 1536) -> str:
        """
        Generate Milvus collection name for this scope

        Format (without collection_name - default):
        - PRIVATE: {user_id}_chunks_{dimension}
        - SHARED: {org_id}_shared_chunks_{dimension}

        Format (with collection_name):
        - PRIVATE: {user_id}_col_{collection_name}_chunks_{dimension}
        - SHARED: {org_id}_col_{collection_name}_chunks_{dimension}

        Note: UUID dashes are converted to underscores for Milvus compatibility
        (Milvus only allows letters, numbers, and underscores)

        Args:
            dimension: Embedding dimension (default: 1536 for OpenAI)

        Returns:
            Collection name string (safe for Milvus)
        """
        if self.scope_type == DataScope.PRIVATE:
            # User ID is globally unique
            safe_user_id = self.user_id.replace('-', '_')
            if self.collection_name:
                # Sanitize collection name (Turkish chars, spaces, special chars -> safe)
                safe_collection = self._sanitize_collection_name(self.collection_name)
                # Prefix with "user_" to ensure it starts with a letter (Milvus requirement)
                return f"user_{safe_user_id}_col_{safe_collection}_chunks_{dimension}"
            # Default collection - also prefix with "user_" for consistency
            return f"user_{safe_user_id}_chunks_{dimension}"
        elif self.scope_type == DataScope.SHARED:
            # Organization shared collection
            safe_org_id = self.organization_id.replace('-', '_')
            if self.collection_name:
                # Sanitize collection name (Turkish chars, spaces, special chars -> safe)
                safe_collection = self._sanitize_collection_name(self.collection_name)
                # Prefix with "org_" to ensure it starts with a letter (Milvus requirement)
                return f"org_{safe_org_id}_col_{safe_collection}_chunks_{dimension}"
            # Default shared collection - prefix with "org_" for consistency (was missing!)
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

        Folder structure with org/user hierarchy:
        - PRIVATE (default): users/{user_id}/{category}/
        - PRIVATE (collection): users/{user_id}/collections/{collection_name}/{category}/
        - SHARED (default): shared/{category}/
        - SHARED (collection): shared/collections/{collection_name}/{category}/

        Args:
            category: Storage category ("docs" or "chunks")

        Returns:
            Object prefix string (folder path with trailing slash)

        Examples:
            Private docs: "users/17d0faab-0830-4007-8ed6-73cfd049505b/docs/"
            Private collection: "users/17d0faab-0830-4007-8ed6-73cfd049505b/collections/legal-research/docs/"
            Shared chunks: "shared/chunks/"
            Shared collection: "shared/collections/contracts/chunks/"
        """
        if self.scope_type == DataScope.PRIVATE:
            if self.collection_name:
                return f"users/{self.user_id}/collections/{self.collection_name}/{category}/"
            return f"users/{self.user_id}/{category}/"
        elif self.scope_type == DataScope.SHARED:
            if self.collection_name:
                return f"shared/collections/{self.collection_name}/{category}/"
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
