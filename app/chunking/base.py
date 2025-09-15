"""
Base classes and interfaces for chunking
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


@dataclass
class Chunk:
    """Data class for text chunks"""
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    metadata: Dict[str, Any]
    token_count: int
    char_count: int


class ChunkingMethod(Enum):
    """Enumeration of available chunking methods"""
    TOKEN = "token"
    CHARACTER = "character"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"
    DOCUMENT = "document"
    HYBRID = "hybrid"


class BaseChunker(ABC):
    """Abstract base class for all chunkers"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize base chunker

        Args:
            chunk_size: Target size for chunks
            chunk_overlap: Overlap between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Split text into chunks

        Args:
            text: Text to chunk
            document_id: Document identifier
            metadata: Optional metadata to attach to chunks

        Returns:
            List of Chunk objects
        """
        pass

    @abstractmethod
    def chunk_pages(
        self,
        pages: List[Any],
        document_id: str,
        preserve_pages: bool = True
    ) -> List[Chunk]:
        """
        Chunk multiple pages of text

        Args:
            pages: List of page objects with text
            document_id: Document identifier
            preserve_pages: Whether to preserve page boundaries

        Returns:
            List of Chunk objects
        """
        pass

    def _generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """
        Generate unique chunk identifier

        Args:
            document_id: Document identifier
            chunk_index: Index of chunk in document

        Returns:
            Unique chunk ID
        """
        return f"{document_id}_chunk_{chunk_index:04d}"