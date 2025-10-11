"""
Pipeline stages for ingest orchestrator

Each stage is isolated and handles a specific part of the ingestion pipeline.
Stages can be modified independently without affecting other stages.
"""
from app.core.orchestrator.stages.base import PipelineStage, StageResult

__all__ = [
    'PipelineStage',
    'StageResult',
]
