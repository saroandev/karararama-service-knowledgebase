"""
Document request schemas
"""
from pydantic import BaseModel, Field, field_validator


class PresignedUrlRequest(BaseModel):
    """Request model for generating presigned URLs for document viewing"""
    document_url: str = Field(
        ...,
        description="Document URL from citations (can be collection or external source)",
        min_length=1
    )
    expires_seconds: int = Field(
        default=3600,
        ge=300,  # Minimum 5 minutes
        le=86400,  # Maximum 24 hours
        description="Presigned URL expiry time in seconds (default: 1 hour)"
    )

    @field_validator('document_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that document_url is not empty"""
        if not v or not v.strip():
            raise ValueError("document_url cannot be empty")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_url": "http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf?X-Amz-Algorithm=...",
                "expires_seconds": 3600
            }
        }
    }
