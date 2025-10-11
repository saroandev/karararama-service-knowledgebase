"""
Base interface for pipeline stages

This module defines the contract that all pipeline stages must follow.
Each stage is isolated and can be modified without affecting other stages.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

from app.core.orchestrator.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """
    Result of a pipeline stage execution

    Attributes:
        success: Whether the stage completed successfully
        stage_name: Name of the stage that produced this result
        message: Human-readable message about the result
        error: Error message if stage failed
        metadata: Additional metadata about stage execution
    """
    success: bool
    stage_name: str
    message: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None

    def __str__(self) -> str:
        status = "✅ SUCCESS" if self.success else "❌ FAILED"
        msg = self.message or self.error or "No details"
        return f"[{self.stage_name}] {status}: {msg}"


class PipelineStage(ABC):
    """
    Abstract base class for all pipeline stages

    Each stage must implement:
    - execute(): Process the context and return result
    - rollback(): Undo changes if pipeline fails (optional)

    Stages are executed sequentially by the IngestOrchestrator.
    Each stage reads from previous stage outputs in context and writes its own output.
    """

    def __init__(self):
        """Initialize stage with logger"""
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Stage name (used for logging and tracking)

        Returns:
            Human-readable stage name
        """
        pass

    @abstractmethod
    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute the stage

        This method should:
        1. Read required inputs from context
        2. Perform stage-specific processing
        3. Write outputs to context
        4. Return StageResult indicating success/failure

        Args:
            context: Pipeline context with inputs and outputs from previous stages

        Returns:
            StageResult indicating success or failure

        Raises:
            Exception: If critical error occurs during execution
        """
        pass

    async def rollback(self, context: PipelineContext) -> None:
        """
        Rollback changes made by this stage

        Called when pipeline fails after this stage has completed.
        Default implementation does nothing (no rollback).

        Override this method if your stage makes changes that need to be undone:
        - Delete uploaded files
        - Remove database entries
        - Clean up temporary resources

        Args:
            context: Pipeline context with execution state
        """
        self.logger.info(f"[{self.name}] No rollback implemented, skipping")

    async def _execute_with_tracking(self, context: PipelineContext) -> StageResult:
        """
        Internal wrapper that adds tracking and error handling

        This method should not be overridden. It provides:
        - Automatic stage start/completion tracking
        - Error handling and logging
        - Execution time measurement

        Args:
            context: Pipeline context

        Returns:
            StageResult from execute() method
        """
        # Mark stage as started
        context.mark_stage_started(self.name)
        self.logger.info(f"🚀 [{self.name}] Starting execution")

        try:
            # Execute stage
            result = await self.execute(context)

            if result.success:
                # Mark as completed
                context.mark_stage_completed(self.name)
                self.logger.info(f"✅ [{self.name}] Completed successfully: {result.message}")
            else:
                # Mark as failed
                context.mark_stage_failed(self.name, result.error or "Unknown error")
                self.logger.error(f"❌ [{self.name}] Failed: {result.error}")

            return result

        except Exception as e:
            # Unexpected error
            error_msg = f"Unexpected error in {self.name}: {str(e)}"
            context.mark_stage_failed(self.name, error_msg)
            self.logger.exception(f"❌ [{self.name}] Exception occurred")

            return StageResult(
                success=False,
                stage_name=self.name,
                error=error_msg
            )

    def validate_input(self, context: PipelineContext, *required_fields: str) -> Optional[str]:
        """
        Helper method to validate required context fields

        Args:
            context: Pipeline context
            *required_fields: Names of required fields in context

        Returns:
            Error message if validation fails, None if all fields present
        """
        for field in required_fields:
            if not hasattr(context, field) or getattr(context, field) is None:
                return f"Required field '{field}' is missing from context"
        return None

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"

    def __repr__(self) -> str:
        return self.__str__()
