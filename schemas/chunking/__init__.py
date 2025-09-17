"""
Chunking schemas for text processing
"""
# Base schemas
from schemas.chunking.base import (
    ChunkingMethod,
    ChunkMetadata,
    Chunk,
    ChunkingConfig,
    ChunkingResult
)

# Text chunking
from schemas.chunking.text import (
    TextChunkConfig,
    TextChunkResult,
    TextChunkingStrategy
)

# Semantic chunking
from schemas.chunking.semantic import (
    SemanticChunkConfig,
    SemanticChunkResult,
    SemanticAnalysis,
    SemanticChunkingStrategy
)

# Document chunking
from schemas.chunking.document import (
    DocumentChunkConfig,
    DocumentElement,
    DocumentStructure,
    DocumentChunkResult
)

# Hybrid chunking
from schemas.chunking.hybrid import (
    HybridChunkConfig,
    HybridChunkResult,
    HybridChunkingStrategy,
    HybridAnalysis
)

__all__ = [
    # Base
    "ChunkingMethod",
    "ChunkMetadata",
    "Chunk",
    "ChunkingConfig",
    "ChunkingResult",
    # Text
    "TextChunkConfig",
    "TextChunkResult",
    "TextChunkingStrategy",
    # Semantic
    "SemanticChunkConfig",
    "SemanticChunkResult",
    "SemanticAnalysis",
    "SemanticChunkingStrategy",
    # Document
    "DocumentChunkConfig",
    "DocumentElement",
    "DocumentStructure",
    "DocumentChunkResult",
    # Hybrid
    "HybridChunkConfig",
    "HybridChunkResult",
    "HybridChunkingStrategy",
    "HybridAnalysis",
]

# Convenience factory functions
def create_chunk_config(method: ChunkingMethod = ChunkingMethod.TOKEN, **kwargs) -> ChunkingConfig:
    """
    Factory function to create appropriate chunking config based on method

    Args:
        method: The chunking method to use
        **kwargs: Additional configuration parameters

    Returns:
        Appropriate ChunkingConfig subclass instance
    """
    if method == ChunkingMethod.TOKEN or method == ChunkingMethod.CHARACTER:
        return TextChunkConfig(method=method, **kwargs)
    elif method == ChunkingMethod.SEMANTIC:
        return SemanticChunkConfig(**kwargs)
    elif method == ChunkingMethod.DOCUMENT:
        return DocumentChunkConfig(**kwargs)
    elif method == ChunkingMethod.HYBRID:
        return HybridChunkConfig(**kwargs)
    else:
        return ChunkingConfig(method=method, **kwargs)


def get_default_config(content_type: str = "general") -> ChunkingConfig:
    """
    Get default chunking configuration based on content type

    Args:
        content_type: Type of content (general, technical, legal, medical)

    Returns:
        Recommended ChunkingConfig for the content type
    """
    configs = {
        "general": TextChunkConfig(
            chunk_size=512,
            chunk_overlap=50,
            preserve_sentences=True
        ),
        "technical": DocumentChunkConfig(
            chunk_size=600,
            chunk_overlap=100,
            preserve_sections=True,
            preserve_tables=True
        ),
        "legal": DocumentChunkConfig(
            chunk_size=800,
            chunk_overlap=150,
            preserve_sections=True,
            extract_metadata=True
        ),
        "medical": HybridChunkConfig(
            primary_method=ChunkingMethod.SEMANTIC,
            secondary_method=ChunkingMethod.DOCUMENT,
            chunk_size=700,
            chunk_overlap=100
        )
    }

    return configs.get(content_type, configs["general"])