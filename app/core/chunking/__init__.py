"""
Chunking module - Modular text chunking with backward compatibility

This module provides various text chunking strategies for RAG systems.
All imports from the old app.chunk module are preserved for backward compatibility.
"""
import logging
from typing import Optional

from app.config import settings
from app.core.chunking.base import Chunk, BaseChunker, ChunkingMethod
from app.core.chunking.text_chunker import TextChunker
from app.core.chunking.semantic_chunker import SemanticChunker
from app.core.chunking.document_chunker import DocumentBasedChunker
from app.core.chunking.hybrid_chunker import HybridChunker

logger = logging.getLogger(__name__)


# Factory functions for backward compatibility
def get_default_chunker():
    """
    Get the default chunker based on configuration

    Returns:
        Default chunker instance
    """
    logger.info(f"Creating default chunker with method: {settings.DEFAULT_CHUNKING_METHOD}")
    return TextChunker(
        chunk_size=settings.DEFAULT_CHUNK_SIZE,
        chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
        method=settings.DEFAULT_CHUNKING_METHOD
    )


def get_document_chunker(chunk_size: int = 512, chunk_overlap: int = 50):
    """
    Get a document-based chunker

    Args:
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks

    Returns:
        DocumentBasedChunker instance
    """
    return DocumentBasedChunker(chunk_size, chunk_overlap)


def get_semantic_chunker(max_chunk_size: int = None):
    """
    Get a semantic chunker

    Args:
        max_chunk_size: Maximum chunk size

    Returns:
        SemanticChunker instance
    """
    max_chunk_size = max_chunk_size or settings.MAX_CHUNK_SIZE
    return SemanticChunker(max_chunk_size)


def get_hybrid_chunker(
    chunk_size: int = None,
    chunk_overlap: int = None,
    primary_method: str = "semantic",
    fallback_method: str = "token"
):
    """
    Get a hybrid chunker

    Args:
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
        primary_method: Primary chunking method
        fallback_method: Fallback method

    Returns:
        HybridChunker instance
    """
    return HybridChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        primary_method=primary_method,
        fallback_method=fallback_method
    )


# Create singleton instances for backward compatibility
default_chunker = get_default_chunker()

# Export all public APIs
__all__ = [
    # Classes
    'Chunk',
    'BaseChunker',
    'ChunkingMethod',
    'TextChunker',
    'SemanticChunker',
    'DocumentBasedChunker',
    'HybridChunker',
    # Factory functions
    'get_default_chunker',
    'get_document_chunker',
    'get_semantic_chunker',
    'get_hybrid_chunker',
    # Singleton
    'default_chunker'
]

logger.info("Chunking module initialized with modular architecture")