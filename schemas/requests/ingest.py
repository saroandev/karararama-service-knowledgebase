"""
Ingest request schemas
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request model for document ingestion"""
    # This is primarily used for request validation
    # File upload is handled via FastAPI's UploadFile
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the document")

    class Config:
        schema_extra = {
            "example": {
                "metadata": {
                    "category": "technical",
                    "tags": ["rag", "ai", "nlp"]
                }
            }
        }