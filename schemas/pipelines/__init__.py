"""
Pipeline schemas for ingestion and query processing
"""

from typing import Union

# Ingest pipeline schemas
from schemas.pipelines.ingest import (
    IngestStage,
    IngestStatus,
    IngestPipelineConfig,
    DocumentIngestRequest,
    IngestStageResult,
    IngestPipelineResult,
    BatchIngestRequest,
    BatchIngestResult,
    IngestMonitoring,
    IngestValidation,
    IngestCallback
)

# Query pipeline schemas
from schemas.pipelines.query import (
    QueryStage,
    QueryMode,
    QueryPipelineConfig,
    QueryRequest,
    RetrievalStageResult,
    RerankingStageResult,
    GenerationStageResult,
    QueryPipelineResult,
    StreamingQueryResult,
    ConversationalContext,
    MultiHopQuery,
    QueryAnalytics,
    QueryOptimization,
    QueryFeedback,
    QueryBatch,
    QueryBatchResult
)

__all__ = [
    # Ingest
    "IngestStage",
    "IngestStatus",
    "IngestPipelineConfig",
    "DocumentIngestRequest",
    "IngestStageResult",
    "IngestPipelineResult",
    "BatchIngestRequest",
    "BatchIngestResult",
    "IngestMonitoring",
    "IngestValidation",
    "IngestCallback",
    # Query
    "QueryStage",
    "QueryMode",
    "QueryPipelineConfig",
    "QueryRequest",
    "RetrievalStageResult",
    "RerankingStageResult",
    "GenerationStageResult",
    "QueryPipelineResult",
    "StreamingQueryResult",
    "ConversationalContext",
    "MultiHopQuery",
    "QueryAnalytics",
    "QueryOptimization",
    "QueryFeedback",
    "QueryBatch",
    "QueryBatchResult",
]


# Helper functions
def create_ingest_pipeline_config(
    store_original: bool = True,
    enable_chunking: bool = True,
    enable_embeddings: bool = True
) -> IngestPipelineConfig:
    """
    Create a default ingestion pipeline configuration

    Args:
        store_original: Store original documents
        enable_chunking: Enable text chunking
        enable_embeddings: Enable embedding generation

    Returns:
        IngestPipelineConfig
    """
    from schemas.pipelines.ingest import IngestPipelineConfig
    from schemas.chunking.base import ChunkingConfig
    from schemas.embeddings.base import EmbeddingConfig

    chunking_config = None
    if enable_chunking:
        chunking_config = ChunkingConfig(
            chunk_size=500,
            chunk_overlap=100,
            chunking_method="token"
        )

    embedding_config = None
    if enable_embeddings:
        embedding_config = EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536
        )

    return IngestPipelineConfig(
        parsing_enabled=True,
        chunking_config=chunking_config,
        embedding_config=embedding_config,
        store_original=store_original,
        store_chunks=enable_chunking,
        store_embeddings=enable_embeddings
    )


def create_query_pipeline_config(
    mode: str = "simple",
    enable_reranking: bool = False,
    top_k: int = 10
) -> QueryPipelineConfig:
    """
    Create a default query pipeline configuration

    Args:
        mode: Query mode (simple, hybrid, multi_hop, conversational)
        enable_reranking: Enable result reranking
        top_k: Number of results to retrieve

    Returns:
        QueryPipelineConfig
    """
    from schemas.pipelines.query import QueryPipelineConfig, QueryMode
    from schemas.retrieval.reranker import RerankerConfig

    reranker_config = None
    if enable_reranking:
        reranker_config = RerankerConfig(
            type="cross_encoder",
            model="ms-marco-MiniLM-L-6-v2",
            top_n=5
        )

    return QueryPipelineConfig(
        mode=QueryMode(mode),
        retrieval_enabled=True,
        top_k=top_k,
        reranking_enabled=enable_reranking,
        reranker_config=reranker_config,
        generation_enabled=True
    )


def create_document_ingest_request(
    document_id: str,
    file_name: str,
    file_path: str = None,
    file_content: bytes = None,
    metadata: dict = None
) -> DocumentIngestRequest:
    """
    Create a document ingestion request

    Args:
        document_id: Document identifier
        file_name: File name
        file_path: Path to file
        file_content: File content as bytes
        metadata: Document metadata

    Returns:
        DocumentIngestRequest
    """
    from schemas.pipelines.ingest import DocumentIngestRequest

    return DocumentIngestRequest(
        document_id=document_id,
        file_name=file_name,
        file_path=file_path,
        file_content=file_content,
        metadata=metadata or {}
    )


def create_query_request(
    query: str,
    user_id: str = None,
    session_id: str = None,
    filters: dict = None
) -> QueryRequest:
    """
    Create a query request

    Args:
        query: User query
        user_id: User identifier
        session_id: Session identifier
        filters: Optional filters

    Returns:
        QueryRequest
    """
    from schemas.pipelines.query import QueryRequest
    import uuid

    return QueryRequest(
        query=query,
        query_id=str(uuid.uuid4()),
        user_id=user_id,
        session_id=session_id,
        document_filters=filters
    )


def track_pipeline_progress(
    pipeline_result: Union[IngestPipelineResult, QueryPipelineResult]
) -> dict:
    """
    Track pipeline progress and return summary

    Args:
        pipeline_result: Pipeline result object

    Returns:
        Progress summary dictionary
    """
    from schemas.pipelines.ingest import IngestPipelineResult, IngestStatus
    from schemas.pipelines.query import QueryPipelineResult

    if isinstance(pipeline_result, IngestPipelineResult):
        completed_stages = sum(
            1 for stage in pipeline_result.stages
            if stage.status == IngestStatus.COMPLETED
        )
        total_stages = len(pipeline_result.stages)

        return {
            "type": "ingest",
            "document_id": pipeline_result.document_id,
            "status": pipeline_result.status,
            "progress_percentage": (completed_stages / total_stages * 100) if total_stages > 0 else 0,
            "completed_stages": completed_stages,
            "total_stages": total_stages,
            "chunks_created": pipeline_result.chunks_created,
            "embeddings_created": pipeline_result.embeddings_created,
            "duration_ms": pipeline_result.total_duration_ms
        }

    elif isinstance(pipeline_result, QueryPipelineResult):
        stages_completed = []
        if pipeline_result.retrieval_result:
            stages_completed.append("retrieval")
        if pipeline_result.reranking_result:
            stages_completed.append("reranking")
        if pipeline_result.generation_result:
            stages_completed.append("generation")

        return {
            "type": "query",
            "query_id": pipeline_result.query_id,
            "query": pipeline_result.query,
            "stages_completed": stages_completed,
            "sources_found": len(pipeline_result.sources),
            "confidence": pipeline_result.confidence_score,
            "duration_ms": pipeline_result.total_time_ms
        }

    return {}


def estimate_pipeline_time(
    pipeline_config: Union[IngestPipelineConfig, QueryPipelineConfig],
    input_size: int = None
) -> float:
    """
    Estimate pipeline execution time

    Args:
        pipeline_config: Pipeline configuration
        input_size: Input size (bytes for ingest, tokens for query)

    Returns:
        Estimated time in milliseconds
    """
    from schemas.pipelines.ingest import IngestPipelineConfig
    from schemas.pipelines.query import QueryPipelineConfig

    if isinstance(pipeline_config, IngestPipelineConfig):
        # Estimate ingest time based on stages and input size
        base_time = 100  # Base overhead

        if pipeline_config.parsing_enabled:
            # Parsing time depends on file size
            parse_time = (input_size or 1000000) / 10000  # ~100ms per MB
            base_time += parse_time

        if pipeline_config.chunking_config:
            # Chunking time
            base_time += 200

        if pipeline_config.embedding_config:
            # Embedding time (depends on batch size)
            base_time += 500

        if pipeline_config.store_embeddings:
            # Vector DB storage time
            base_time += 300

        return base_time

    elif isinstance(pipeline_config, QueryPipelineConfig):
        # Estimate query time
        base_time = 50  # Base overhead

        if pipeline_config.retrieval_enabled:
            # Retrieval time
            base_time += 200

        if pipeline_config.reranking_enabled:
            # Reranking time
            base_time += 300

        if pipeline_config.generation_enabled:
            # Generation time (depends on max_tokens)
            base_time += pipeline_config.max_tokens * 0.5

        return base_time

    return 1000  # Default estimate