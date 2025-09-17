"""
Pipeline package for orchestrating RAG operations

This package provides modular pipeline implementations for:
- Document ingestion
- Query processing
- Batch operations
- Conversational queries
"""
import logging
from typing import Optional

from app.pipelines.base import (
    AbstractPipeline,
    CompositePipeline,
    PipelineProgress,
    PipelineResult,
    PipelineStage
)
from app.pipelines.ingest_pipeline import (
    IngestPipeline,
    BatchIngestPipeline
)
from app.pipelines.query_pipeline import (
    QueryPipeline,
    MultiQueryPipeline,
    ConversationalQueryPipeline
)
from app.pipelines.utils import (
    retry_async,
    retry_sync,
    measure_time,
    validate_file_size,
    validate_file_type,
    batch_process,
    batch_process_async,
    create_pipeline_metadata,
    format_error_response,
    estimate_processing_time,
    calculate_batch_size
)

logger = logging.getLogger(__name__)


# Create default pipeline instances
_default_ingest_pipeline: Optional[IngestPipeline] = None
_default_query_pipeline: Optional[QueryPipeline] = None


def get_ingest_pipeline() -> IngestPipeline:
    """
    Get or create default ingest pipeline

    Returns:
        IngestPipeline instance
    """
    global _default_ingest_pipeline
    if _default_ingest_pipeline is None:
        _default_ingest_pipeline = IngestPipeline()
        logger.info("Created default ingest pipeline")
    return _default_ingest_pipeline


def get_query_pipeline() -> QueryPipeline:
    """
    Get or create default query pipeline

    Returns:
        QueryPipeline instance
    """
    global _default_query_pipeline
    if _default_query_pipeline is None:
        _default_query_pipeline = QueryPipeline()
        logger.info("Created default query pipeline")
    return _default_query_pipeline


def create_pipeline(pipeline_type: str, **kwargs) -> AbstractPipeline:
    """
    Factory function to create pipeline instances

    Args:
        pipeline_type: Type of pipeline to create
            - 'ingest': Document ingestion pipeline
            - 'batch_ingest': Batch document ingestion
            - 'query': Query processing pipeline
            - 'multi_query': Multiple query processing
            - 'conversational': Conversational query pipeline
        **kwargs: Additional arguments for pipeline constructor

    Returns:
        Pipeline instance

    Raises:
        ValueError: If pipeline_type is unknown
    """
    pipeline_map = {
        'ingest': IngestPipeline,
        'batch_ingest': BatchIngestPipeline,
        'query': QueryPipeline,
        'multi_query': MultiQueryPipeline,
        'conversational': ConversationalQueryPipeline
    }

    pipeline_class = pipeline_map.get(pipeline_type)
    if not pipeline_class:
        raise ValueError(f"Unknown pipeline type: {pipeline_type}")

    logger.info(f"Creating {pipeline_type} pipeline")
    return pipeline_class(**kwargs)


# Default pipeline instances (lazy loading)
default_ingest_pipeline = property(lambda self: get_ingest_pipeline())
default_query_pipeline = property(lambda self: get_query_pipeline())


# Export all public classes and functions
__all__ = [
    # Base classes
    'AbstractPipeline',
    'CompositePipeline',
    'PipelineProgress',
    'PipelineResult',
    'PipelineStage',
    # Ingest pipelines
    'IngestPipeline',
    'BatchIngestPipeline',
    # Query pipelines
    'QueryPipeline',
    'MultiQueryPipeline',
    'ConversationalQueryPipeline',
    # Factory functions
    'create_pipeline',
    'get_ingest_pipeline',
    'get_query_pipeline',
    # Utilities
    'retry_async',
    'retry_sync',
    'measure_time',
    'validate_file_size',
    'validate_file_type',
    'batch_process',
    'batch_process_async',
    'create_pipeline_metadata',
    'format_error_response',
    'estimate_processing_time',
    'calculate_batch_size'
]