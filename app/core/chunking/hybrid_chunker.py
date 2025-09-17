"""
Hybrid chunking implementation combining multiple strategies
"""
import logging
from typing import List, Dict, Any, Optional

from app.config import settings
from app.core.chunking.base import BaseChunker, Chunk
from app.core.chunking.text_chunker import TextChunker
from app.core.chunking.semantic_chunker import SemanticChunker
from app.core.chunking.utils import merge_chunks

logger = logging.getLogger(__name__)


class HybridChunker(BaseChunker):
    """Combines multiple chunking strategies for optimal results"""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        primary_method: str = "semantic",
        fallback_method: str = "token"
    ):
        """
        Initialize hybrid chunker

        Args:
            chunk_size: Target chunk size
            chunk_overlap: Overlap between chunks
            primary_method: Primary chunking method
            fallback_method: Fallback method if primary fails
        """
        chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
        super().__init__(chunk_size, chunk_overlap)

        self.primary_method = primary_method
        self.fallback_method = fallback_method

        # Initialize component chunkers
        self.semantic_chunker = SemanticChunker(max_chunk_size=chunk_size)
        self.text_chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            method=fallback_method
        )

    def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Apply hybrid chunking strategy

        Args:
            text: Text to chunk
            document_id: Document identifier
            metadata: Optional metadata

        Returns:
            List of Chunk objects
        """
        chunks = []

        try:
            # Try primary method first
            if self.primary_method == "semantic":
                chunks = self.semantic_chunker.chunk_text(text, document_id, metadata)
            else:
                chunks = self.text_chunker.chunk_text(text, document_id, metadata)

            # Validate chunks
            if not chunks:
                raise ValueError("Primary method produced no chunks")

            # Post-process chunks
            chunks = self._post_process_chunks(chunks)

        except Exception as e:
            logger.warning(f"Primary method {self.primary_method} failed: {e}, using fallback")

            # Use fallback method
            try:
                chunks = self.text_chunker.chunk_text(text, document_id, metadata)
            except Exception as fallback_error:
                logger.error(f"Fallback method also failed: {fallback_error}")
                raise

        # Update metadata to indicate hybrid chunking
        for chunk in chunks:
            chunk.metadata["chunk_method"] = "hybrid"
            chunk.metadata["primary_method"] = self.primary_method
            chunk.metadata["fallback_used"] = len(chunks) == 0

        logger.info(f"Created {len(chunks)} chunks using hybrid strategy")
        return chunks

    def _post_process_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Post-process chunks to optimize quality

        Args:
            chunks: Initial chunks

        Returns:
            Optimized chunks
        """
        if not chunks:
            return chunks

        # Merge very small chunks
        min_size = settings.MIN_CHUNK_SIZE
        processed_chunks = []
        buffer_chunk = None

        for chunk in chunks:
            if chunk.token_count < min_size:
                # Too small, try to merge
                if buffer_chunk is None:
                    buffer_chunk = chunk
                else:
                    # Merge with buffer
                    buffer_chunk.text += "\n\n" + chunk.text
                    buffer_chunk.token_count += chunk.token_count
                    buffer_chunk.char_count += chunk.char_count

                    # Update metadata
                    if "merged_from" not in buffer_chunk.metadata:
                        buffer_chunk.metadata["merged_from"] = []
                    buffer_chunk.metadata["merged_from"].append(chunk.chunk_id)

                    # Check if buffer is now large enough
                    if buffer_chunk.token_count >= min_size:
                        processed_chunks.append(buffer_chunk)
                        buffer_chunk = None
            else:
                # Chunk is fine
                if buffer_chunk:
                    # Add pending buffer first
                    processed_chunks.append(buffer_chunk)
                    buffer_chunk = None
                processed_chunks.append(chunk)

        # Add any remaining buffer
        if buffer_chunk:
            processed_chunks.append(buffer_chunk)

        # Re-index chunks
        for i, chunk in enumerate(processed_chunks):
            chunk.chunk_index = i

        return processed_chunks

    def chunk_pages(
        self,
        pages: List[Any],
        document_id: str,
        preserve_pages: bool = True
    ) -> List[Chunk]:
        """
        Chunk multiple pages using hybrid strategy

        Args:
            pages: List of page objects
            document_id: Document identifier
            preserve_pages: Whether to preserve page boundaries

        Returns:
            List of Chunk objects
        """
        all_chunks = []

        if preserve_pages:
            # Process each page separately
            for page in pages:
                page_text = page.text if hasattr(page, 'text') else str(page)
                page_number = page.page_number if hasattr(page, 'page_number') else len(all_chunks) + 1

                page_metadata = {
                    "page_number": page_number
                }
                if hasattr(page, 'metadata'):
                    page_metadata.update(page.metadata)

                page_chunks = self.chunk_text(page_text, document_id, page_metadata)
                all_chunks.extend(page_chunks)
        else:
            # Combine all pages
            combined_text = "\n\n".join(
                page.text if hasattr(page, 'text') else str(page)
                for page in pages
            )
            all_chunks = self.chunk_text(combined_text, document_id)

        # Re-index all chunks
        for i, chunk in enumerate(all_chunks):
            chunk.chunk_index = i

        return all_chunks