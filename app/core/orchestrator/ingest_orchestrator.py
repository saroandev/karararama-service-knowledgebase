"""
Ingest Orchestrator - Coordinates all stages of document ingestion pipeline

This orchestrator executes stages sequentially and handles failures with rollback.
"""
import logging
from typing import List, Optional
from dataclasses import dataclass

from app.core.orchestrator.pipeline_context import PipelineContext
from app.core.orchestrator.stages.base import PipelineStage
from app.core.orchestrator.stages.validation_stage import ValidationStage
from app.core.orchestrator.stages.parsing_stage import ParsingStage
from app.core.orchestrator.stages.chunking_stage import ChunkingStage
from app.core.orchestrator.stages.embedding_stage import EmbeddingStage
from app.core.orchestrator.stages.indexing_stage import IndexingStage
from app.core.orchestrator.stages.storage_stage import StorageStage
from app.core.orchestrator.stages.consume_stage import ConsumeStage

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """
    Result of document ingestion pipeline

    Attributes:
        success: Whether ingestion succeeded
        document_id: Document identifier
        chunks_created: Number of chunks created
        processing_time: Total processing time in seconds
        message: Human-readable result message
        error: Error message if failed
        context_summary: Summary of pipeline execution
    """
    success: bool
    document_id: str
    chunks_created: int = 0
    processing_time: float = 0.0
    message: str = ""
    error: Optional[str] = None
    context_summary: Optional[dict] = None


class IngestOrchestrator:
    """
    Orchestrates the document ingestion pipeline

    Pipeline stages (executed sequentially):
    1. ValidationStage: Validate document
    2. ParsingStage: Extract text from PDF
    3. ChunkingStage: Split text into chunks with token limits
    4. EmbeddingStage: Generate embeddings
    5. IndexingStage: Insert into Milvus
    6. StorageStage: Upload to MinIO
    7. ConsumeStage: Report usage to auth service

    Each stage is isolated and can be modified independently.
    If any stage fails, completed stages are rolled back.
    """

    def __init__(self):
        """Initialize orchestrator with all pipeline stages"""
        self.logger = logging.getLogger(self.__class__.__name__)

        # Create pipeline stages in order
        self.stages: List[PipelineStage] = [
            ValidationStage(),
            ParsingStage(),
            ChunkingStage(),
            EmbeddingStage(),
            IndexingStage(),
            StorageStage(),
            ConsumeStage()
        ]

        self.logger.info(f"🎭 IngestOrchestrator initialized with {len(self.stages)} stages")

    async def process(self, context: PipelineContext) -> IngestResult:
        """
        Execute the entire ingestion pipeline

        Args:
            context: Pipeline context with input data

        Returns:
            IngestResult with success/failure status
        """
        self.logger.info("=" * 80)
        self.logger.info(f"🚀 Starting ingestion pipeline for: {context.filename}")
        self.logger.info(f"📄 Document ID: {context.document_id}")
        self.logger.info(f"👤 User: {context.user.user_id}")
        self.logger.info(f"🏢 Organization: {context.user.organization_id}")
        self.logger.info(f"🎯 Collection: {context.get_collection_name()}")
        self.logger.info("=" * 80)

        # Execute stages sequentially
        for stage in self.stages:
            self.logger.info("")
            self.logger.info(f"⏩ Stage {len(context.completed_stages) + 1}/{len(self.stages)}: {stage.name.upper()}")
            self.logger.info("-" * 80)

            try:
                # Execute stage with automatic tracking
                result = await stage._execute_with_tracking(context)

                # Check if stage succeeded
                if not result.success:
                    # Stage failed - rollback and stop pipeline
                    self.logger.error(f"❌ Pipeline failed at stage: {stage.name}")
                    self.logger.error(f"   Error: {result.error}")

                    # Rollback completed stages
                    await self._rollback_pipeline(context)

                    # Return failure result
                    return IngestResult(
                        success=False,
                        document_id=context.document_id,
                        processing_time=context.get_total_duration(),
                        message=f"Ingestion failed at {stage.name} stage",
                        error=result.error,
                        context_summary=context.to_summary()
                    )

            except Exception as e:
                # Unexpected error during stage execution
                self.logger.exception(f"❌ Unexpected error in stage {stage.name}: {e}")

                # Rollback completed stages
                await self._rollback_pipeline(context)

                # Return failure result
                return IngestResult(
                    success=False,
                    document_id=context.document_id,
                    processing_time=context.get_total_duration(),
                    message=f"Ingestion failed due to unexpected error in {stage.name}",
                    error=str(e),
                    context_summary=context.to_summary()
                )

        # All stages completed successfully!
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY")
        self.logger.info("=" * 80)
        self._log_pipeline_summary(context)

        return IngestResult(
            success=True,
            document_id=context.document_id,
            chunks_created=len(context.chunks) if context.chunks else 0,
            processing_time=context.get_total_duration(),
            message=f"Document successfully ingested with {len(context.chunks) if context.chunks else 0} chunks",
            context_summary=context.to_summary()
        )

    async def _rollback_pipeline(self, context: PipelineContext) -> None:
        """
        Rollback all completed stages in reverse order

        Args:
            context: Pipeline context with execution state
        """
        if not context.completed_stages:
            self.logger.info("🔄 No stages to rollback")
            return

        self.logger.warning("")
        self.logger.warning("=" * 80)
        self.logger.warning("🔄 ROLLING BACK COMPLETED STAGES")
        self.logger.warning("=" * 80)

        # Rollback in reverse order
        for stage in reversed(self.stages):
            if stage.name in context.completed_stages:
                try:
                    self.logger.warning(f"🔄 Rolling back: {stage.name}")
                    await stage.rollback(context)
                except Exception as e:
                    # Log but don't fail on rollback errors
                    self.logger.error(f"❌ Failed to rollback {stage.name}: {e}")

        self.logger.warning("=" * 80)

    def _log_pipeline_summary(self, context: PipelineContext) -> None:
        """
        Log detailed pipeline execution summary

        Args:
            context: Pipeline context with execution results
        """
        summary = context.to_summary()

        self.logger.info("")
        self.logger.info("📊 PIPELINE SUMMARY")
        self.logger.info("-" * 80)
        self.logger.info(f"   Document ID: {summary['document_id']}")
        self.logger.info(f"   Filename: {summary['filename']}")
        self.logger.info(f"   Collection: {summary['collection_name']}")
        self.logger.info(f"   Total Duration: {summary['total_duration_seconds']:.2f}s")
        self.logger.info("")
        self.logger.info(f"   Stages Completed: {len(summary['completed_stages'])}/{len(self.stages)}")
        for stage_name in summary['completed_stages']:
            duration = context.stats.get(f"{stage_name}_duration_seconds", 0)
            self.logger.info(f"      ✅ {stage_name}: {duration:.2f}s")
        self.logger.info("")

        # Document statistics
        self.logger.info(f"   📄 Pages Processed: {summary['pages_processed']}")
        self.logger.info(f"   ✂️  Chunks Created: {summary['chunks_created']}")

        # Detailed stats
        if context.stats:
            self.logger.info("")
            self.logger.info("   📈 Detailed Statistics:")

            if 'total_words' in context.stats:
                self.logger.info(f"      Words Extracted: {context.stats['total_words']:,}")

            if 'avg_chunk_tokens' in context.stats:
                self.logger.info(f"      Avg Tokens/Chunk: {context.stats['avg_chunk_tokens']:.0f}")

            if 'chunk_size_config' in context.stats:
                self.logger.info(f"      Chunk Size Config: {context.stats['chunk_size_config']} tokens")

            if 'chunk_overlap_config' in context.stats:
                self.logger.info(f"      Chunk Overlap: {context.stats['chunk_overlap_config']} tokens")

            if 'embedding_model' in context.stats:
                self.logger.info(f"      Embedding Model: {context.stats['embedding_model']}")

            if 'embedding_dimension' in context.stats:
                self.logger.info(f"      Embedding Dimension: {context.stats['embedding_dimension']}")

        self.logger.info("")
        self.logger.info("=" * 80)

    def get_stage_by_name(self, stage_name: str) -> Optional[PipelineStage]:
        """
        Get a stage by name

        Args:
            stage_name: Name of the stage

        Returns:
            Stage instance or None if not found
        """
        for stage in self.stages:
            if stage.name == stage_name:
                return stage
        return None
