"""
Ingest response schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# Base response class for ingestion
class BaseIngestResponse(BaseModel):
    """Base response model for document ingestion"""
    document_id: str = Field(..., description="Unique document identifier")
    document_title: str = Field(..., description="Document title")
    file_hash: str = Field(..., description="MD5 hash of the file")
    processing_time: float = Field(..., description="Processing time in seconds")
    message: str = Field(..., description="Response message")


# Successful document ingestion
class SuccessfulIngestResponse(BaseIngestResponse):
    """Response for successful document ingestion"""
    success: bool = Field(default=True, description="Success status")
    chunks_created: int = Field(..., description="Number of chunks created")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "doc_abc123",
                "document_title": "Sample Document",
                "file_hash": "5d41402abc4b2a76b9719d911017c592",
                "processing_time": 2.5,
                "message": "Document successfully ingested with 10 chunks",
                "success": True,
                "chunks_created": 10
            }
        }
        }


# Document already exists response
class ExistingDocumentResponse(BaseIngestResponse):
    """Response when document already exists"""
    success: bool = Field(default=False, description="Success status")
    chunks_count: int = Field(default=0, description="Existing chunks count")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "doc_abc123",
                "document_title": "Sample Document",
                "file_hash": "5d41402abc4b2a76b9719d911017c592",
                "processing_time": 0.1,
                "message": "Document already exists in database",
                "success": False,
                "chunks_count": 10
            }
        }
        }


# Failed ingestion response
class FailedIngestResponse(BaseIngestResponse):
    """Response for failed document ingestion"""
    success: bool = Field(default=False, description="Success status")
    error_details: Optional[str] = Field(default=None, description="Detailed error information")

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "",
                "document_title": "",
                "file_hash": "",
                "processing_time": 0.5,
                "message": "Ingest failed: Invalid PDF format",
                "success": False,
                "error_details": "PDF parsing error: Unable to read file"
            }
        }
        }


# Batch ingestion response models
class FileIngestStatus(BaseModel):
    """Status of individual file ingestion in batch processing"""
    filename: str = Field(..., description="Name of the file")
    status: str = Field(..., description="Processing status", pattern="^(success|failed|skipped|processing)$")
    document_id: Optional[str] = Field(default=None, description="Document ID if successful")
    chunks_created: Optional[int] = Field(default=None, description="Chunks created if successful")
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    file_hash: Optional[str] = Field(default=None, description="File hash if processed")


class BatchIngestResponse(BaseModel):
    """Response for batch document ingestion"""
    total_files: int = Field(..., description="Total number of files processed")
    successful: int = Field(..., description="Number of successfully ingested files")
    failed: int = Field(..., description="Number of failed files")
    skipped: int = Field(..., description="Number of skipped files (already existing)")
    results: List[FileIngestStatus] = Field(..., description="Individual file results")
    total_processing_time: float = Field(..., description="Total processing time in seconds")
    message: str = Field(..., description="Summary message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_files": 3,
                "successful": 2,
                "failed": 0,
                "skipped": 1,
                "results": [
                    {
                        "filename": "doc1.pdf",
                        "status": "success",
                        "document_id": "doc_123",
                        "chunks_created": 10,
                        "processing_time": 2.5,
                        "file_hash": "abc123"
                    }
                ],
                "total_processing_time": 5.3,
                "message": "Processed 3 files: 2 successful, 0 failed, 1 skipped"
            }
        }
    }
