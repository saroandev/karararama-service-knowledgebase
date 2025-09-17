"""
Document-structure-aware chunking implementation
"""
import hashlib
import logging
from typing import List, Dict, Any, Optional

from app.config import settings
from app.core.chunking.base import BaseChunker, Chunk
from app.core.chunking.utils import token_count, clean_text

logger = logging.getLogger(__name__)


class DocumentBasedChunker(BaseChunker):
    """Document-based chunking that preserves document structure"""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """
        Initialize document-based chunker

        Args:
            chunk_size: Target chunk size
            chunk_overlap: Overlap between chunks
        """
        chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
        super().__init__(chunk_size, chunk_overlap)

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs

        Args:
            text: Input text

        Returns:
            List of paragraphs
        """
        # Clean text first
        text = clean_text(text)

        # Split by double newlines
        paragraphs = text.split('\n\n')

        # Filter empty paragraphs
        return [p.strip() for p in paragraphs if p.strip()]

    def _create_chunk(
        self,
        text: str,
        document_id: str,
        index: int,
        metadata: Dict[str, Any]
    ) -> Chunk:
        """
        Create a chunk object

        Args:
            text: Chunk text
            document_id: Document ID
            index: Chunk index
            metadata: Chunk metadata

        Returns:
            Chunk object
        """
        chunk_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        chunk_id = f"chunk_{document_id}_{index:04d}_{chunk_hash}"

        chunk_metadata = {
            "document_id": document_id,
            "chunk_index": index,
            "chunk_method": "document",
            "chunk_size_target": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            **metadata
        }

        return Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=index,
            text=text,
            metadata=chunk_metadata,
            token_count=token_count(text),
            char_count=len(text)
        )

    def chunk_by_document(
        self,
        pages: List[Any],
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk pages while preserving document structure

        Args:
            pages: List of PageContent objects
            document_id: Document identifier
            metadata: Optional metadata

        Returns:
            List of Chunk objects organized by document structure
        """
        chunks = []
        chunk_index = 0

        for page in pages:
            # Process each page separately to preserve document structure
            page_text = page.text if hasattr(page, 'text') else str(page)
            page_number = page.page_number if hasattr(page, 'page_number') else len(chunks) + 1

            page_metadata = {
                "page_number": page_number,
                "document_structure": "page_based"
            }

            # Add page metadata if available
            if hasattr(page, 'metadata'):
                page_metadata.update(page.metadata)

            # Add global metadata
            if metadata:
                page_metadata.update(metadata)

            # Clean the text
            page_text = clean_text(page_text)

            # Split page into smaller chunks if needed
            if token_count(page_text) > self.chunk_size:
                # Split by paragraphs first
                paragraphs = self._split_by_paragraphs(page_text)

                current_chunk = ""
                current_tokens = 0

                for paragraph in paragraphs:
                    para_tokens = token_count(paragraph)

                    if current_tokens + para_tokens <= self.chunk_size:
                        current_chunk += paragraph + "\n\n"
                        current_tokens += para_tokens
                    else:
                        # Save current chunk if not empty
                        if current_chunk:
                            chunk = self._create_chunk(
                                current_chunk.strip(),
                                document_id,
                                chunk_index,
                                page_metadata
                            )
                            chunks.append(chunk)
                            chunk_index += 1

                        # Handle overlap
                        if self.chunk_overlap > 0 and current_chunk:
                            # Keep last part for overlap
                            overlap_text = current_chunk.split()[-self.chunk_overlap:]
                            current_chunk = " ".join(overlap_text) + "\n\n" + paragraph
                            current_tokens = token_count(current_chunk)
                        else:
                            current_chunk = paragraph + "\n\n"
                            current_tokens = para_tokens

                # Add remaining chunk
                if current_chunk.strip():
                    chunk = self._create_chunk(
                        current_chunk.strip(),
                        document_id,
                        chunk_index,
                        page_metadata
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            else:
                # Page is small enough to be a single chunk
                chunk = self._create_chunk(
                    page_text,
                    document_id,
                    chunk_index,
                    page_metadata
                )
                chunks.append(chunk)
                chunk_index += 1

        logger.info(f"Created {len(chunks)} document-based chunks")
        return chunks

    def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk single text string

        Args:
            text: Text to chunk
            document_id: Document identifier
            metadata: Optional metadata

        Returns:
            List of Chunk objects
        """
        # Create a fake page object for compatibility
        class FakePage:
            def __init__(self, text):
                self.text = text
                self.page_number = 1
                self.metadata = {}

        fake_page = FakePage(text)
        return self.chunk_by_document([fake_page], document_id, metadata)

    def chunk_pages(
        self,
        pages: List[Any],
        document_id: str,
        preserve_pages: bool = True
    ) -> List[Chunk]:
        """
        Chunk multiple pages of text

        Args:
            pages: List of page objects
            document_id: Document identifier
            preserve_pages: Whether to preserve page boundaries

        Returns:
            List of Chunk objects
        """
        if preserve_pages:
            # Use document-based chunking
            return self.chunk_by_document(pages, document_id)
        else:
            # Combine all pages and chunk as single text
            combined_text = "\n\n".join(
                page.text if hasattr(page, 'text') else str(page)
                for page in pages
            )
            return self.chunk_text(combined_text, document_id)