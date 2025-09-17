"""
Backward compatibility module for document ingestion.

This file is kept for backward compatibility.
All imports from 'app.ingest' will be redirected to the new pipeline structure.
New code should use 'from app.pipelines import IngestPipeline' directly.
"""
import logging
import warnings
import asyncio
from typing import Dict, Any, Optional, Callable, BinaryIO
from dataclasses import dataclass

# Import from new location
from app.pipelines import (
    IngestPipeline as ModernIngestPipeline,
    BatchIngestPipeline,
    PipelineProgress,
    PipelineResult
)

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "Importing from app.ingest is deprecated. Use app.pipelines instead.",
    DeprecationWarning,
    stacklevel=2
)


# Legacy IngestionProgress for backward compatibility
@dataclass
class IngestionProgress:
    """Legacy progress tracking for ingestion"""
    stage: str
    progress: float
    message: str
    current_step: int
    total_steps: int
    document_id: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_pipeline_progress(cls, progress: PipelineProgress):
        """Convert from new PipelineProgress format"""
        return cls(
            stage=progress.stage,
            progress=progress.progress,
            message=progress.message,
            current_step=progress.current_step,
            total_steps=progress.total_steps,
            document_id=progress.metadata.get('document_id') if progress.metadata else None,
            error=progress.error
        )


class IngestionPipeline:
    """
    Legacy IngestionPipeline class for backward compatibility.
    This wraps the new IngestPipeline implementation.
    """

    def __init__(self):
        """Initialize ingestion pipeline"""
        warnings.warn(
            "IngestionPipeline is deprecated. Use IngestPipeline from app.pipelines",
            DeprecationWarning,
            stacklevel=2
        )

        # Use new pipeline implementation
        self._pipeline = ModernIngestPipeline()

        # Legacy attributes for compatibility
        self.storage = self._pipeline.storage
        self.parser = self._pipeline.parser
        self.chunker = self._pipeline.chunker
        self.embedder = self._pipeline.embedder
        self.indexer = self._pipeline.indexer

        # Progress tracking
        self.progress_callback: Optional[Callable[[IngestionProgress], None]] = None
        self.current_progress = IngestionProgress("idle", 0.0, "Ready", 0, 0)

    def set_progress_callback(self, callback: Callable[[IngestionProgress], None]):
        """Set callback for progress updates"""
        self.progress_callback = callback

        # Wrapper to convert new progress format to legacy
        def wrapper(progress: PipelineProgress):
            legacy_progress = IngestionProgress.from_pipeline_progress(progress)
            self.current_progress = legacy_progress
            if self.progress_callback:
                self.progress_callback(legacy_progress)

        self._pipeline.set_progress_callback(wrapper)

    def _update_progress(self, stage: str, progress: float, message: str,
                        current_step: int = 0, total_steps: int = 0,
                        error: Optional[str] = None):
        """Update progress (legacy method)"""
        self.current_progress = IngestionProgress(
            stage=stage,
            progress=progress,
            message=message,
            current_step=current_step,
            total_steps=total_steps,
            document_id=self.current_progress.document_id,
            error=error
        )

        if self.progress_callback:
            self.progress_callback(self.current_progress)

        logger.info(f"[{stage}] {progress:.1f}% - {message}")

    async def ingest_document(
        self,
        file_obj: BinaryIO,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        chunk_strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest a single document (legacy method)

        Args:
            file_obj: File object to ingest
            filename: Original filename
            metadata: Additional metadata
            chunk_size: Override chunk size
            chunk_overlap: Override chunk overlap
            chunk_strategy: Override chunking strategy

        Returns:
            Result dictionary with document_id and statistics
        """
        # Run pipeline
        result = await self._pipeline.run(
            file_obj=file_obj,
            filename=filename,
            metadata=metadata or {},
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunk_strategy=chunk_strategy
        )

        # Convert result to legacy format
        if result.success:
            return result.data
        else:
            raise Exception(result.error)

    async def ingest_documents_batch(
        self,
        files: list,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Ingest multiple documents (legacy method)

        Args:
            files: List of (file_obj, filename) tuples
            metadata: Common metadata for all documents
            chunk_size: Override chunk size
            chunk_overlap: Override chunk overlap

        Returns:
            Result dictionary with statistics
        """
        # Convert to new format
        file_list = []
        for item in files:
            if isinstance(item, tuple):
                file_obj, filename = item
            else:
                file_obj = item.get('file_obj')
                filename = item.get('filename')

            file_list.append({
                'file_obj': file_obj,
                'filename': filename,
                'metadata': metadata or {},
                'chunk_size': chunk_size,
                'chunk_overlap': chunk_overlap
            })

        # Use batch pipeline
        batch_pipeline = BatchIngestPipeline()
        result = await batch_pipeline.run(files=file_list)

        # Convert result to legacy format
        if result.success:
            return result.data
        else:
            raise Exception(result.error)

    def ingest_document_sync(
        self,
        file_obj: BinaryIO,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        chunk_strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronous version of ingest_document (legacy method)

        Args:
            file_obj: File object to ingest
            filename: Original filename
            metadata: Additional metadata
            chunk_size: Override chunk size
            chunk_overlap: Override chunk overlap
            chunk_strategy: Override chunking strategy

        Returns:
            Result dictionary with document_id and statistics
        """
        return asyncio.run(self.ingest_document(
            file_obj, filename, metadata,
            chunk_size, chunk_overlap, chunk_strategy
        ))


# Create singleton instance for backward compatibility
ingestion_pipeline = IngestionPipeline()


# Export everything for backward compatibility
__all__ = [
    'IngestionPipeline',
    'IngestionProgress',
    'ingestion_pipeline',
    # Also export new names
    'ModernIngestPipeline',
    'BatchIngestPipeline',
    'PipelineProgress',
    'PipelineResult'
]