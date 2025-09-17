"""
Base classes for pipeline implementations
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Pipeline stage enumeration"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class PipelineProgress:
    """Progress tracking for pipelines"""
    stage: str
    progress: float
    message: str
    current_step: int
    total_steps: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "metadata": self.metadata or {}
        }


@dataclass
class PipelineResult:
    """Result of pipeline execution"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class AbstractPipeline(ABC):
    """Abstract base class for all pipeline implementations"""

    def __init__(self, name: str = None):
        """
        Initialize the pipeline

        Args:
            name: Pipeline name for logging
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

        # Progress tracking
        self.progress_callback: Optional[Callable[[PipelineProgress], None]] = None
        self.current_progress = PipelineProgress(
            stage=PipelineStage.IDLE.value,
            progress=0.0,
            message="Ready",
            current_step=0,
            total_steps=0
        )

        # Timing
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # State
        self.is_running = False
        self.is_cancelled = False

    def set_progress_callback(self, callback: Callable[[PipelineProgress], None]):
        """
        Set callback for progress updates

        Args:
            callback: Function to call with progress updates
        """
        self.progress_callback = callback

    def update_progress(
        self,
        stage: str,
        progress: float,
        message: str,
        current_step: int = 0,
        total_steps: int = 0,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Update progress and call callback if set

        Args:
            stage: Current stage name
            progress: Progress percentage (0-100)
            message: Progress message
            current_step: Current step number
            total_steps: Total number of steps
            error: Error message if any
            metadata: Additional metadata
        """
        self.current_progress = PipelineProgress(
            stage=stage,
            progress=progress,
            message=message,
            current_step=current_step,
            total_steps=total_steps,
            started_at=self.start_time,
            completed_at=self.end_time,
            error=error,
            metadata=metadata
        )

        if self.progress_callback:
            try:
                self.progress_callback(self.current_progress)
            except Exception as e:
                self.logger.error(f"Error in progress callback: {e}")

        log_level = logging.ERROR if error else logging.INFO
        self.logger.log(log_level, f"[{stage}] {progress:.1f}% - {message}")

    @abstractmethod
    async def execute(self, **kwargs) -> PipelineResult:
        """
        Execute the pipeline

        Args:
            **kwargs: Pipeline-specific arguments

        Returns:
            PipelineResult with execution details
        """
        pass

    @abstractmethod
    def validate_inputs(self, **kwargs) -> bool:
        """
        Validate pipeline inputs

        Args:
            **kwargs: Pipeline-specific arguments

        Returns:
            True if inputs are valid, False otherwise

        Raises:
            ValueError: If inputs are invalid with details
        """
        pass

    async def run(self, **kwargs) -> PipelineResult:
        """
        Run the pipeline with validation and error handling

        Args:
            **kwargs: Pipeline-specific arguments

        Returns:
            PipelineResult with execution details
        """
        self.is_running = True
        self.is_cancelled = False
        self.start_time = datetime.now()
        self.end_time = None

        try:
            # Update initial progress
            self.update_progress(
                PipelineStage.INITIALIZING.value,
                0.0,
                f"Starting {self.name} pipeline..."
            )

            # Validate inputs
            if not self.validate_inputs(**kwargs):
                raise ValueError("Input validation failed")

            # Execute pipeline
            self.update_progress(
                PipelineStage.PROCESSING.value,
                10.0,
                "Executing pipeline..."
            )

            result = await self.execute(**kwargs)

            # Mark as completed
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()

            if result.success:
                self.update_progress(
                    PipelineStage.COMPLETED.value,
                    100.0,
                    f"Pipeline completed successfully in {duration:.2f}s"
                )
            else:
                self.update_progress(
                    PipelineStage.ERROR.value,
                    self.current_progress.progress,
                    f"Pipeline failed: {result.error}",
                    error=result.error
                )

            # Add duration to result
            result.duration_seconds = duration

            return result

        except Exception as e:
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds() if self.start_time else 0

            error_msg = str(e)
            self.logger.error(f"Pipeline error: {error_msg}", exc_info=True)

            self.update_progress(
                PipelineStage.ERROR.value,
                self.current_progress.progress,
                f"Pipeline error: {error_msg}",
                error=error_msg
            )

            return PipelineResult(
                success=False,
                error=error_msg,
                duration_seconds=duration
            )
        finally:
            self.is_running = False

    def cancel(self):
        """Cancel the pipeline execution"""
        if self.is_running:
            self.is_cancelled = True
            self.update_progress(
                PipelineStage.CANCELLED.value,
                self.current_progress.progress,
                "Pipeline cancelled by user"
            )
            self.logger.info(f"Pipeline {self.name} cancelled")

    def reset(self):
        """Reset pipeline state"""
        self.is_running = False
        self.is_cancelled = False
        self.start_time = None
        self.end_time = None
        self.current_progress = PipelineProgress(
            stage=PipelineStage.IDLE.value,
            progress=0.0,
            message="Ready",
            current_step=0,
            total_steps=0
        )


class CompositePipeline(AbstractPipeline):
    """
    A pipeline that runs multiple sub-pipelines in sequence
    """

    def __init__(self, name: str = None, pipelines: List[AbstractPipeline] = None):
        """
        Initialize composite pipeline

        Args:
            name: Pipeline name
            pipelines: List of sub-pipelines to execute
        """
        super().__init__(name)
        self.pipelines = pipelines or []

    def add_pipeline(self, pipeline: AbstractPipeline):
        """Add a sub-pipeline"""
        self.pipelines.append(pipeline)

    async def execute(self, **kwargs) -> PipelineResult:
        """
        Execute all sub-pipelines in sequence

        Args:
            **kwargs: Arguments passed to all pipelines

        Returns:
            Combined result from all pipelines
        """
        total_pipelines = len(self.pipelines)
        results = []

        for i, pipeline in enumerate(self.pipelines):
            if self.is_cancelled:
                return PipelineResult(
                    success=False,
                    error="Pipeline cancelled",
                    data={"completed_pipelines": i, "results": results}
                )

            # Update progress
            self.update_progress(
                PipelineStage.PROCESSING.value,
                (i / total_pipelines) * 90 + 10,  # 10-100% range
                f"Running {pipeline.name} ({i+1}/{total_pipelines})"
            )

            # Run sub-pipeline
            result = await pipeline.run(**kwargs)
            results.append(result)

            # Stop if sub-pipeline failed
            if not result.success:
                return PipelineResult(
                    success=False,
                    error=f"Sub-pipeline {pipeline.name} failed: {result.error}",
                    data={"failed_pipeline": pipeline.name, "results": results}
                )

        # All pipelines succeeded
        return PipelineResult(
            success=True,
            data={"completed_pipelines": total_pipelines, "results": results}
        )

    def validate_inputs(self, **kwargs) -> bool:
        """Validate inputs for all sub-pipelines"""
        for pipeline in self.pipelines:
            if not pipeline.validate_inputs(**kwargs):
                return False
        return True