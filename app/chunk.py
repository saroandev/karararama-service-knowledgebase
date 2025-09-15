"""
Backward compatibility shim for chunk module

This file maintains backward compatibility by re-exporting everything
from the new modular chunking package. All imports from app.chunk
will continue to work without any code changes.
"""

# Re-export everything from the new modular structure
from app.chunking import *
from app.chunking import (
    Chunk,
    TextChunker,
    SemanticChunker,
    DocumentBasedChunker,
    HybridChunker,
    get_default_chunker,
    get_document_chunker,
    get_semantic_chunker,
    get_hybrid_chunker,
    default_chunker
)

# Ensure all old imports continue to work
__all__ = [
    'Chunk',
    'TextChunker',
    'SemanticChunker',
    'DocumentBasedChunker',
    'HybridChunker',
    'get_default_chunker',
    'get_document_chunker',
    'get_semantic_chunker',
    'get_hybrid_chunker',
    'default_chunker'
]