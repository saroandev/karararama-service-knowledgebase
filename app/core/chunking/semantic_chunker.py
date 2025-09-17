"""
Semantic-based chunking implementation
"""
import hashlib
import logging
import re
from typing import List, Dict, Any, Optional

from app.config import settings
from app.core.chunking.base import BaseChunker, Chunk
from app.core.chunking.utils import token_count, clean_text

logger = logging.getLogger(__name__)


class SemanticChunker(BaseChunker):
    """Advanced semantic-based text chunking"""

    def __init__(self, max_chunk_size: int = None):
        """
        Initialize semantic chunker

        Args:
            max_chunk_size: Maximum chunk size in tokens
        """
        max_chunk_size = max_chunk_size or settings.MAX_CHUNK_SIZE
        super().__init__(chunk_size=max_chunk_size, chunk_overlap=0)
        self.max_chunk_size = max_chunk_size
        self.similarity_threshold = settings.SEMANTIC_SIMILARITY_THRESHOLD

    def _detect_paragraphs(self, text: str) -> List[str]:
        """
        Detect natural paragraph boundaries

        Args:
            text: Input text

        Returns:
            List of paragraphs
        """
        # Clean text first
        text = clean_text(text)

        # Split by double newlines first
        paragraphs = text.split('\n\n')

        # Further split long paragraphs by single newlines if needed
        refined_paragraphs = []
        for para in paragraphs:
            if len(para) > self.max_chunk_size * 4:  # ~4 chars per token
                # Split by single newlines
                sub_paras = para.split('\n')
                refined_paragraphs.extend(sub_paras)
            else:
                refined_paragraphs.append(para)

        # Filter out empty paragraphs
        return [p.strip() for p in refined_paragraphs if p.strip()]

    def _group_paragraphs(self, paragraphs: List[str]) -> List[List[str]]:
        """
        Group paragraphs into semantic chunks

        Args:
            paragraphs: List of paragraphs

        Returns:
            List of paragraph groups
        """
        if not paragraphs:
            return []

        groups = []
        current_group = []
        current_size = 0

        for para in paragraphs:
            para_size = token_count(para)

            # Check if adding this paragraph would exceed max size
            if current_size + para_size > self.max_chunk_size and current_group:
                # Save current group and start new one
                groups.append(current_group)
                current_group = [para]
                current_size = para_size
            else:
                # Add to current group
                current_group.append(para)
                current_size += para_size

        # Add last group
        if current_group:
            groups.append(current_group)

        return groups

    def _detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect document sections based on headers

        Args:
            text: Input text

        Returns:
            List of sections with metadata
        """
        sections = []

        # Common header patterns
        header_patterns = [
            r'^#{1,6}\s+(.+)$',  # Markdown headers
            r'^([A-Z][A-Z0-9\s]+)$',  # ALL CAPS headers
            r'^(\d+\.?\s+.+)$',  # Numbered headers
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):?\s*$',  # Title Case headers
        ]

        lines = text.split('\n')
        current_section = {'title': 'Introduction', 'content': [], 'level': 0}

        for line in lines:
            is_header = False

            for pattern in header_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    # Save current section
                    if current_section['content']:
                        sections.append({
                            'title': current_section['title'],
                            'content': '\n'.join(current_section['content']),
                            'level': current_section['level']
                        })

                    # Start new section
                    current_section = {
                        'title': match.group(1) if match.lastindex else line.strip(),
                        'content': [],
                        'level': self._detect_header_level(line)
                    }
                    is_header = True
                    break

            if not is_header:
                current_section['content'].append(line)

        # Add last section
        if current_section['content']:
            sections.append({
                'title': current_section['title'],
                'content': '\n'.join(current_section['content']),
                'level': current_section['level']
            })

        return sections

    def _detect_header_level(self, line: str) -> int:
        """Detect header level (1-6)"""
        # Markdown style
        if line.startswith('#'):
            return len(line.split()[0])
        # Numbered style
        if re.match(r'^\d+\.', line):
            return line.count('.') + 1
        # Default
        return 1

    def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Split text based on semantic boundaries

        Args:
            text: Text to chunk
            document_id: Document identifier
            metadata: Optional metadata

        Returns:
            List of Chunk objects
        """
        # Detect sections if possible
        sections = self._detect_sections(text)

        if sections:
            # Use section-based chunking
            all_chunks = []
            for section in sections:
                section_paragraphs = self._detect_paragraphs(section['content'])
                section_groups = self._group_paragraphs(section_paragraphs)

                for group in section_groups:
                    chunk_text = "\n\n".join(group)
                    chunk_metadata = {
                        'section_title': section['title'],
                        'section_level': section['level']
                    }
                    if metadata:
                        chunk_metadata.update(metadata)

                    all_chunks.append(self._create_chunk(
                        chunk_text,
                        document_id,
                        len(all_chunks),
                        chunk_metadata
                    ))
        else:
            # Fall back to paragraph-based chunking
            paragraphs = self._detect_paragraphs(text)
            semantic_groups = self._group_paragraphs(paragraphs)

            all_chunks = []
            for i, group in enumerate(semantic_groups):
                chunk_text = "\n\n".join(group)
                chunk_metadata = {
                    'paragraph_count': len(group)
                }
                if metadata:
                    chunk_metadata.update(metadata)

                all_chunks.append(self._create_chunk(
                    chunk_text,
                    document_id,
                    i,
                    chunk_metadata
                ))

        logger.info(f"Created {len(all_chunks)} semantic chunks")
        return all_chunks

    def _create_chunk(
        self,
        text: str,
        document_id: str,
        index: int,
        metadata: Dict[str, Any]
    ) -> Chunk:
        """Create a chunk object"""
        chunk_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        chunk_id = f"chunk_{document_id}_{index:04d}_{chunk_hash}"

        chunk_metadata = {
            "document_id": document_id,
            "chunk_index": index,
            "chunk_method": "semantic",
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

    def chunk_pages(
        self,
        pages: List[Any],
        document_id: str,
        preserve_pages: bool = True
    ) -> List[Chunk]:
        """
        Chunk multiple pages using semantic analysis

        Args:
            pages: List of page objects
            document_id: Document identifier
            preserve_pages: Whether to preserve page boundaries

        Returns:
            List of Chunk objects
        """
        # Combine all pages for semantic analysis
        combined_text = "\n\n".join(
            page.text if hasattr(page, 'text') else str(page)
            for page in pages
        )

        # Perform semantic chunking
        chunks = self.chunk_text(combined_text, document_id)

        # Add page information if needed
        if preserve_pages:
            for chunk in chunks:
                # Simple heuristic: assign to first page where text appears
                for i, page in enumerate(pages):
                    page_text = page.text if hasattr(page, 'text') else str(page)
                    if chunk.text[:100] in page_text:
                        chunk.metadata['primary_page'] = i + 1
                        break

        return chunks