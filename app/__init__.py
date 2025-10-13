"""
RAG Application Package

This is the main application package with modular architecture.
All components are organized into specialized subpackages.
"""

# Core Components - New modular structure
from app.core.embeddings import (
    create_embedding_generator,
    default_embedding_generator
)

from app.core.generation import (
    create_generator,
    create_answer_generator,  # Alias for backward compatibility
    default_generator
)

from app.core.parsing import (
    create_parser,
    default_parser
)

from app.core.indexing import (
    create_indexer,
    default_indexer
)

from app.core.retrieval import (
    create_retriever,
    default_retriever
)

# Storage Components
from app.core.storage import storage

# Chunking Components
from app.core.chunking import (
    get_default_chunker,
    TextChunker,
    SemanticChunker,
    HybridChunker
)

# Pipeline Components
from app.pipelines import (
    IngestPipeline,
    QueryPipeline,
    BatchIngestPipeline,
    ConversationalQueryPipeline
)

# Utilities
from app.utils import (
    setup_logger,
    get_logger,
    retry,
    async_retry,
    measure_time,
    validate_pdf_file,
    generate_document_id,
    generate_chunk_id
)

# Configuration
from app.config import settings

__version__ = "1.0.0"

__all__ = [
    # Configuration
    'settings',
    # Core Components
    'create_embedding_generator',
    'default_embedding_generator',
    'create_generator',
    'create_answer_generator',
    'default_generator',
    'create_parser',
    'default_parser',
    'create_indexer',
    'default_indexer',
    'create_retriever',
    'default_retriever',
    # Storage
    'storage',
    # Chunking
    'get_default_chunker',
    'TextChunker',
    'SemanticChunker',
    'HybridChunker',
    # Pipelines
    'IngestPipeline',
    'QueryPipeline',
    'BatchIngestPipeline',
    'ConversationalQueryPipeline',
    # Utilities
    'setup_logger',
    'get_logger',
    'retry',
    'async_retry',
    'measure_time',
    'validate_pdf_file',
    'generate_document_id',
    'generate_chunk_id'
]