"""
Pipeline context for ingest orchestrator

This module defines the shared context that flows through all pipeline stages.
Each stage reads from and writes to this context, maintaining state across the pipeline.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import numpy as np

from schemas.parsing.page import PageContent
from schemas.internal.chunk import SimpleChunk
from schemas.validation.validation_result import ValidationResult
from schemas.api.requests.scope import ScopeIdentifier
from app.core.auth import UserContext


@dataclass
class PipelineContext:
    """
    Shared context passed through all ingest pipeline stages

    This context maintains state as document flows through:
    Validation → Parsing → Chunking → Embedding → Indexing → Storage → Consume

    Each stage populates its output fields and subsequent stages read from previous outputs.
    """

    # ========== INPUT DATA (Provided at pipeline start) ==========
    file_data: bytes
    filename: str
    document_id: str
    scope_identifier: ScopeIdentifier
    user: UserContext

    # ========== STAGE OUTPUTS (Populated during pipeline execution) ==========

    # Stage 1: Validation
    validation_result: Optional[ValidationResult] = None

    # Stage 2: Parsing
    pages: Optional[List[PageContent]] = None

    # Stage 3: Chunking
    chunks: Optional[List[SimpleChunk]] = None

    # Stage 4: Embedding
    embeddings: Optional[List[np.ndarray]] = None

    # Stage 5: Indexing (Milvus)
    milvus_insert_result: Optional[Dict[str, Any]] = None

    # Stage 6: Storage (MinIO)
    storage_paths: Optional[Dict[str, str]] = None

    # Stage 7: Usage Consumption (Auth Service)
    usage_result: Optional[Dict[str, Any]] = None

    # ========== METADATA & TRACKING ==========

    # Pipeline execution tracking
    pipeline_start_time: datetime = field(default_factory=datetime.now)
    current_stage: Optional[str] = None
    completed_stages: List[str] = field(default_factory=list)

    # Error handling
    error: Optional[str] = None
    error_stage: Optional[str] = None

    # Statistics (populated during execution)
    stats: Dict[str, Any] = field(default_factory=dict)

    # ========== HELPER METHODS ==========

    def mark_stage_started(self, stage_name: str):
        """Mark a stage as started"""
        self.current_stage = stage_name
        self.stats[f"{stage_name}_start_time"] = datetime.now()

    def mark_stage_completed(self, stage_name: str):
        """Mark a stage as completed"""
        self.completed_stages.append(stage_name)
        self.stats[f"{stage_name}_end_time"] = datetime.now()

        # Calculate stage duration
        start_time = self.stats.get(f"{stage_name}_start_time")
        end_time = self.stats.get(f"{stage_name}_end_time")
        if start_time and end_time:
            duration = (end_time - start_time).total_seconds()
            self.stats[f"{stage_name}_duration_seconds"] = duration

    def mark_stage_failed(self, stage_name: str, error_message: str):
        """Mark a stage as failed"""
        self.error_stage = stage_name
        self.error = error_message
        self.stats[f"{stage_name}_failed"] = True

    def get_total_duration(self) -> float:
        """Get total pipeline duration in seconds"""
        if not hasattr(self, 'pipeline_start_time'):
            return 0.0
        return (datetime.now() - self.pipeline_start_time).total_seconds()

    def is_stage_completed(self, stage_name: str) -> bool:
        """Check if a stage has been completed"""
        return stage_name in self.completed_stages

    def get_collection_name(self, dimension: int = 1536) -> str:
        """
        Get Milvus collection name for this context

        Uses scope_identifier to generate the appropriate collection name:
        - If collection_name is specified: uses named collection
        - If collection_name is None: uses default collection

        Args:
            dimension: Embedding dimension (default: 1536 for OpenAI)

        Returns:
            Collection name (e.g., "user_{user_id}_chunks_1536" or "user_{user_id}_col_{name}_chunks_1536")
        """
        return self.scope_identifier.get_collection_name(dimension)

    def get_bucket_name(self) -> str:
        """Get MinIO bucket name for this context (org-based)"""
        return self.scope_identifier.get_bucket_name()

    def get_object_prefix(self, category: str = "docs") -> str:
        """
        Get MinIO object prefix (folder path) for this context

        Args:
            category: Storage category ("docs" or "chunks")

        Returns:
            Object prefix with trailing slash
        """
        return self.scope_identifier.get_object_prefix(category)

    def to_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of pipeline execution

        Returns:
            Dictionary with pipeline execution summary
        """
        # Get validation status safely (might be string or enum)
        validation_status = None
        if self.validation_result:
            if hasattr(self.validation_result.status, 'value'):
                validation_status = self.validation_result.status.value
            else:
                validation_status = self.validation_result.status

        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "collection_name": self.get_collection_name(),
            "completed_stages": self.completed_stages,
            "current_stage": self.current_stage,
            "total_duration_seconds": self.get_total_duration(),
            "chunks_created": len(self.chunks) if self.chunks else 0,
            "pages_processed": len(self.pages) if self.pages else 0,
            "error": self.error,
            "error_stage": self.error_stage,
            "validation_status": validation_status,
            "stats": self.stats
        }
