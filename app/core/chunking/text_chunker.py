"""
Text-based chunking implementations
"""
import hashlib
import logging
from typing import List, Dict, Any, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

# We'll use tiktoken for token-based splitting instead of SentenceTransformers
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from app.config import settings
from app.core.chunking.base import BaseChunker, Chunk
from app.core.chunking.utils import token_count, clean_text, calculate_page_boundaries, get_pages_for_position

logger = logging.getLogger(__name__)


class TextChunker(BaseChunker):
    """Text-based chunking with various methods"""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        method: str = None
    ):
        """
        Initialize text chunker

        Args:
            chunk_size: Target chunk size (tokens or characters based on method)
            chunk_overlap: Overlap between chunks
            method: Chunking method ("token", "character", "sentence")
        """
        # Use settings if not provided
        chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
        method = method or settings.DEFAULT_CHUNKING_METHOD

        super().__init__(chunk_size, chunk_overlap)
        self.method = method
        self.splitter = self._create_splitter()

    def _create_splitter(self):
        """Create the appropriate text splitter based on method"""
        if self.method == "token":
            # Use character-based splitter with token counting
            # This avoids TensorFlow dependency
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size * 4,  # Approximate 4 chars per token
                chunk_overlap=self.chunk_overlap * 4,
                separators=["\n\n", "\n", ". ", " ", ""],
                length_function=len  # Use character count
            )
        elif self.method == "character":
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                length_function=len
            )
        elif self.method == "sentence":
            # Custom sentence-based splitter
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", ". ", "! ", "? "],
                length_function=len  # Use character count
            )
        else:
            raise ValueError(f"Unknown chunking method: {self.method}")

    def _token_count(self, text: str) -> int:
        """Count tokens in text"""
        return token_count(text)

    def _simple_split(self, text: str) -> List[str]:
        """Simple fallback splitting method"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0

        for word in words:
            word_size = len(word) // 4  # Approximate token count
            if current_size + word_size > self.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Overlap
                overlap_size = self.chunk_overlap
                current_chunk = current_chunk[-overlap_size:] if overlap_size > 0 else []
                current_size = sum(len(w) // 4 for w in current_chunk)

            current_chunk.append(word)
            current_size += word_size

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

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
        if not text or not text.strip():
            return []

        # Clean text
        text = clean_text(text)

        # Split text
        try:
            text_chunks = self.splitter.split_text(text)
        except Exception as e:
            logger.error(f"Error splitting text with {self.method} method: {e}")
            # Fallback to simple splitting
            text_chunks = self._simple_split(text)

        # Create chunk objects
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            chunk_hash = hashlib.md5(chunk_text.encode()).hexdigest()[:16]
            chunk_id = f"chunk_{document_id}_{i:04d}_{chunk_hash}"

            chunk_metadata = {
                "document_id": document_id,
                "chunk_index": i,
                "chunk_method": self.method,
                "chunk_size_target": self.chunk_size,
                "chunk_overlap": self.chunk_overlap
            }

            # Add provided metadata
            if metadata:
                chunk_metadata.update(metadata)

            chunks.append(Chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=i,
                text=chunk_text,
                metadata=chunk_metadata,
                token_count=self._token_count(chunk_text),
                char_count=len(chunk_text)
            ))

        logger.info(f"Created {len(chunks)} chunks using {self.method} method")
        return chunks

    def chunk_pages(
        self,
        pages: List[Any],
        document_id: str,
        preserve_pages: bool = True
    ) -> List[Chunk]:
        """
        Chunk multiple pages of text

        Args:
            pages: List of PageContent objects
            document_id: Document identifier
            preserve_pages: Whether to preserve page boundaries

        Returns:
            List of Chunk objects
        """
        all_chunks = []

        if preserve_pages:
            # Chunk each page separately
            for page in pages:
                page_text = page.text if hasattr(page, 'text') else str(page)
                page_number = page.page_number if hasattr(page, 'page_number') else len(all_chunks) + 1

                page_chunks = self.chunk_text(
                    page_text,
                    document_id,
                    metadata={
                        "page_number": page_number,
                        **(page.metadata if hasattr(page, 'metadata') else {})
                    }
                )
                all_chunks.extend(page_chunks)
        else:
            # Combine all pages and chunk together
            combined_text = "\n\n".join(
                page.text if hasattr(page, 'text') else str(page)
                for page in pages
            )

            # Track page boundaries
            page_boundaries = calculate_page_boundaries(pages)

            chunks = self.chunk_text(combined_text, document_id)

            # Add page information to chunks
            for chunk in chunks:
                try:
                    start_pos = combined_text.index(chunk.text)
                    page_nums = get_pages_for_position(start_pos, page_boundaries)
                    chunk.metadata["page_numbers"] = page_nums
                except ValueError:
                    chunk.metadata["page_numbers"] = [1]

            all_chunks = chunks

        return all_chunks