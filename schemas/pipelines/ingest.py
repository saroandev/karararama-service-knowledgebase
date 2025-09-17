"""
Document ingestion pipeline schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum

from schemas.parsing.document import DocumentMetadata, DocumentProcessingResult
from schemas.chunking.base import ChunkingConfig, ChunkingResult
from schemas.embeddings.base import EmbeddingConfig
from schemas.storage.minio import StorageOperation
from schemas.storage.milvus import VectorData


class IngestStage(str, Enum):
    """Stages in the ingestion pipeline"""
    UPLOAD = "upload"
    PARSE = "parse"
    CHUNK = "chunk"
    EMBED = "embed"
    STORE = "store"
    INDEX = "index"
    VALIDATE = "validate"
    COMPLETE = "complete"


class IngestStatus(str, Enum):
    """Status of ingestion process"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class IngestPipelineConfig(BaseModel):
    """Configuration for ingestion pipeline"""
    # Pipeline settings
    pipeline_name: str = Field(default="default", description="Pipeline name")
    version: str = Field(default="1.0.0", description="Pipeline version")

    # Stage configurations
    parsing_enabled: bool = Field(default=True, description="Enable document parsing")
    chunking_config: Optional[ChunkingConfig] = Field(default=None, description="Chunking configuration")
    embedding_config: Optional[EmbeddingConfig] = Field(default=None, description="Embedding configuration")

    # Storage settings
    store_original: bool = Field(default=True, description="Store original document")
    store_chunks: bool = Field(default=True, description="Store text chunks")
    store_embeddings: bool = Field(default=True, description="Store embeddings in vector DB")

    # Processing options
    batch_size: int = Field(default=100, ge=1, description="Batch size for processing")
    parallel_processing: bool = Field(default=True, description="Enable parallel processing")
    max_workers: int = Field(default=4, ge=1, description="Maximum parallel workers")

    # Error handling
    stop_on_error: bool = Field(default=False, description="Stop pipeline on error")
    retry_failed: bool = Field(default=True, description="Retry failed stages")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")

    # Validation
    validate_input: bool = Field(default=True, description="Validate input documents")
    validate_output: bool = Field(default=True, description="Validate output data")

    # Performance
    timeout_seconds: Optional[int] = Field(default=300, ge=1, description="Pipeline timeout")
    memory_limit_mb: Optional[int] = Field(default=None, ge=100, description="Memory limit in MB")

    class Config:
        validate_assignment = True


class DocumentIngestRequest(BaseModel):
    """Request to ingest a document"""
    document_id: str = Field(..., description="Unique document identifier")
    file_path: Optional[str] = Field(default=None, description="Path to document file")
    file_content: Optional[bytes] = Field(default=None, description="Document content as bytes")
    file_name: str = Field(..., description="Document file name")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    source: Optional[str] = Field(default=None, description="Document source")

    # Processing options
    pipeline_config: Optional[IngestPipelineConfig] = Field(default=None, description="Pipeline config override")
    priority: int = Field(default=0, ge=0, le=10, description="Processing priority")

    # Options
    force_reprocess: bool = Field(default=False, description="Force reprocessing if exists")
    skip_existing: bool = Field(default=True, description="Skip if already processed")

    @validator("file_content")
    def validate_input(cls, v, values):
        """Ensure either file_path or file_content is provided"""
        if not v and not values.get("file_path"):
            raise ValueError("Either file_path or file_content must be provided")
        return v

    class Config:
        validate_assignment = True


class IngestStageResult(BaseModel):
    """Result from a single ingestion stage"""
    stage: IngestStage = Field(..., description="Stage name")
    status: IngestStatus = Field(..., description="Stage status")

    # Timing
    start_time: datetime = Field(..., description="Stage start time")
    end_time: Optional[datetime] = Field(default=None, description="Stage end time")
    duration_ms: Optional[float] = Field(default=None, ge=0, description="Stage duration in ms")

    # Results
    output_data: Optional[Dict[str, Any]] = Field(default=None, description="Stage output data")
    artifacts: List[str] = Field(default_factory=list, description="Created artifacts")

    # Metrics
    items_processed: int = Field(default=0, ge=0, description="Items processed")
    items_failed: int = Field(default=0, ge=0, description="Items failed")

    # Error information
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed error info")

    @validator("duration_ms", always=True)
    def calculate_duration(cls, v, values):
        """Calculate duration from start and end times"""
        if values.get("start_time") and values.get("end_time"):
            delta = values["end_time"] - values["start_time"]
            return delta.total_seconds() * 1000
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class IngestPipelineResult(BaseModel):
    """Complete result from ingestion pipeline"""
    document_id: str = Field(..., description="Document identifier")
    pipeline_id: str = Field(..., description="Pipeline execution ID")
    status: IngestStatus = Field(..., description="Overall pipeline status")

    # Stage results
    stages: List[IngestStageResult] = Field(..., description="Individual stage results")
    current_stage: Optional[IngestStage] = Field(default=None, description="Current processing stage")

    # Timing
    start_time: datetime = Field(..., description="Pipeline start time")
    end_time: Optional[datetime] = Field(default=None, description="Pipeline end time")
    total_duration_ms: Optional[float] = Field(default=None, ge=0, description="Total duration")

    # Output
    document_metadata: Optional[DocumentMetadata] = Field(default=None, description="Document metadata")
    chunks_created: int = Field(default=0, ge=0, description="Number of chunks created")
    embeddings_created: int = Field(default=0, ge=0, description="Number of embeddings created")

    # Storage locations
    original_storage_path: Optional[str] = Field(default=None, description="Original doc storage path")
    chunks_storage_paths: List[str] = Field(default_factory=list, description="Chunk storage paths")
    vector_collection: Optional[str] = Field(default=None, description="Vector DB collection")

    # Metrics
    total_tokens: Optional[int] = Field(default=None, ge=0, description="Total tokens processed")
    total_pages: Optional[int] = Field(default=None, ge=0, description="Total pages processed")
    file_size_bytes: Optional[int] = Field(default=None, ge=0, description="File size in bytes")

    # Error tracking
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="All errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")

    @validator("status", always=True)
    def determine_status(cls, v, values):
        """Determine overall status from stage results"""
        if "stages" in values and values["stages"]:
            statuses = [stage.status for stage in values["stages"]]
            if all(s == IngestStatus.COMPLETED for s in statuses):
                return IngestStatus.COMPLETED
            elif any(s == IngestStatus.FAILED for s in statuses):
                return IngestStatus.FAILED
            elif any(s == IngestStatus.PROCESSING for s in statuses):
                return IngestStatus.PROCESSING
            elif any(s == IngestStatus.PARTIAL for s in statuses):
                return IngestStatus.PARTIAL
        return v or IngestStatus.PENDING

    class Config:
        use_enum_values = True
        validate_assignment = True


class BatchIngestRequest(BaseModel):
    """Request for batch document ingestion"""
    documents: List[DocumentIngestRequest] = Field(..., min_items=1, description="Documents to ingest")
    batch_id: str = Field(..., description="Unique batch identifier")

    # Processing options
    pipeline_config: Optional[IngestPipelineConfig] = Field(default=None, description="Shared pipeline config")
    parallel: bool = Field(default=True, description="Process documents in parallel")
    max_parallel: int = Field(default=5, ge=1, description="Max parallel documents")

    # Error handling
    continue_on_error: bool = Field(default=True, description="Continue processing on errors")
    rollback_on_failure: bool = Field(default=False, description="Rollback batch on failure")

    # Monitoring
    progress_callback: Optional[str] = Field(default=None, description="Progress callback URL")
    notification_email: Optional[str] = Field(default=None, description="Completion notification email")

    class Config:
        validate_assignment = True


class BatchIngestResult(BaseModel):
    """Result from batch ingestion"""
    batch_id: str = Field(..., description="Batch identifier")
    status: IngestStatus = Field(..., description="Overall batch status")

    # Document results
    total_documents: int = Field(..., ge=1, description="Total documents in batch")
    completed: int = Field(default=0, ge=0, description="Successfully completed documents")
    failed: int = Field(default=0, ge=0, description="Failed documents")
    partial: int = Field(default=0, ge=0, description="Partially processed documents")

    # Individual results
    document_results: List[IngestPipelineResult] = Field(..., description="Individual document results")

    # Timing
    start_time: datetime = Field(..., description="Batch start time")
    end_time: Optional[datetime] = Field(default=None, description="Batch end time")
    total_duration_ms: Optional[float] = Field(default=None, ge=0, description="Total duration")
    avg_document_time_ms: Optional[float] = Field(default=None, ge=0, description="Avg time per document")

    # Aggregated metrics
    total_chunks: int = Field(default=0, ge=0, description="Total chunks created")
    total_embeddings: int = Field(default=0, ge=0, description="Total embeddings created")
    total_bytes_processed: int = Field(default=0, ge=0, description="Total bytes processed")

    # Errors
    error_summary: Dict[str, int] = Field(default_factory=dict, description="Error type counts")

    @validator("failed", always=True)
    def calculate_failed(cls, v, values):
        """Calculate failed count"""
        if "total_documents" in values and "completed" in values:
            return values["total_documents"] - values["completed"] - values.get("partial", 0)
        return v or 0

    @validator("avg_document_time_ms", always=True)
    def calculate_avg_time(cls, v, values):
        """Calculate average document processing time"""
        if values.get("total_duration_ms") and values.get("total_documents"):
            return values["total_duration_ms"] / values["total_documents"]
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class IngestMonitoring(BaseModel):
    """Monitoring data for ingestion pipeline"""
    # Current state
    active_pipelines: int = Field(default=0, ge=0, description="Currently active pipelines")
    queued_documents: int = Field(default=0, ge=0, description="Documents in queue")

    # Performance metrics
    avg_document_time_ms: float = Field(..., ge=0, description="Average document processing time")
    avg_chunk_time_ms: float = Field(..., ge=0, description="Average chunk processing time")
    avg_embedding_time_ms: float = Field(..., ge=0, description="Average embedding time")

    # Success rates
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Overall success rate")
    parse_success_rate: float = Field(..., ge=0.0, le=1.0, description="Parsing success rate")
    embedding_success_rate: float = Field(..., ge=0.0, le=1.0, description="Embedding success rate")

    # Resource usage
    cpu_usage_percent: float = Field(..., ge=0.0, le=100.0, description="CPU usage")
    memory_usage_mb: float = Field(..., ge=0, description="Memory usage in MB")
    storage_usage_gb: float = Field(..., ge=0, description="Storage usage in GB")

    # Throughput
    documents_per_minute: float = Field(..., ge=0, description="Documents processed per minute")
    chunks_per_minute: float = Field(..., ge=0, description="Chunks processed per minute")
    embeddings_per_minute: float = Field(..., ge=0, description="Embeddings generated per minute")

    # Error tracking
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Error rate")
    common_errors: Dict[str, int] = Field(default_factory=dict, description="Common error types")

    # Time period
    monitoring_start: datetime = Field(..., description="Monitoring period start")
    monitoring_end: datetime = Field(..., description="Monitoring period end")

    class Config:
        validate_assignment = True


class IngestValidation(BaseModel):
    """Validation rules for ingestion"""
    # Document validation
    allowed_formats: List[str] = Field(
        default_factory=lambda: ["pdf", "txt", "docx", "html", "md"],
        description="Allowed file formats"
    )
    max_file_size_mb: int = Field(default=100, ge=1, description="Maximum file size in MB")
    min_file_size_bytes: int = Field(default=100, ge=1, description="Minimum file size in bytes")

    # Content validation
    min_text_length: int = Field(default=100, ge=1, description="Minimum text length")
    max_text_length: Optional[int] = Field(default=None, ge=1, description="Maximum text length")
    required_metadata: List[str] = Field(default_factory=list, description="Required metadata fields")

    # Chunk validation
    min_chunk_size: int = Field(default=50, ge=1, description="Minimum chunk size in tokens")
    max_chunk_size: int = Field(default=1000, ge=1, description="Maximum chunk size in tokens")

    # Embedding validation
    embedding_dimension: int = Field(default=1536, ge=1, description="Expected embedding dimension")
    max_embedding_norm: Optional[float] = Field(default=None, ge=0, description="Max embedding norm")

    # Quality checks
    check_duplicates: bool = Field(default=True, description="Check for duplicate documents")
    check_language: bool = Field(default=False, description="Validate document language")
    expected_language: Optional[str] = Field(default=None, description="Expected language code")

    def validate_document(self, file_name: str, file_size: int) -> tuple[bool, Optional[str]]:
        """
        Validate a document before ingestion

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check format
        extension = file_name.split('.')[-1].lower() if '.' in file_name else ''
        if extension not in self.allowed_formats:
            return False, f"File format '{extension}' not allowed"

        # Check size
        if file_size > self.max_file_size_mb * 1024 * 1024:
            return False, f"File size exceeds {self.max_file_size_mb}MB limit"

        if file_size < self.min_file_size_bytes:
            return False, f"File size below {self.min_file_size_bytes} bytes minimum"

        return True, None

    class Config:
        validate_assignment = True


class IngestCallback(BaseModel):
    """Callback configuration for ingestion events"""
    callback_url: str = Field(..., description="Callback URL")
    callback_type: Literal["webhook", "function", "queue"] = Field(..., description="Callback type")

    # Events to trigger callbacks
    on_start: bool = Field(default=True, description="Trigger on pipeline start")
    on_complete: bool = Field(default=True, description="Trigger on completion")
    on_error: bool = Field(default=True, description="Trigger on error")
    on_stage_complete: bool = Field(default=False, description="Trigger after each stage")

    # Retry settings
    retry_on_failure: bool = Field(default=True, description="Retry failed callbacks")
    max_retries: int = Field(default=3, ge=0, description="Max callback retries")

    # Authentication
    auth_type: Optional[Literal["bearer", "basic", "api_key"]] = Field(default=None, description="Auth type")
    auth_credentials: Optional[str] = Field(default=None, description="Auth credentials")

    class Config:
        validate_assignment = True