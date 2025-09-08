import hashlib
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    SentenceTransformersTokenTextSplitter
)

logger = logging.getLogger(__name__)


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


class TextChunker:
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        method: str = "token"
    ):
        """
        Initialize text chunker
        
        Args:
            chunk_size: Target chunk size (tokens or characters based on method)
            chunk_overlap: Overlap between chunks
            method: Chunking method ("token", "character", "sentence")
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.method = method
        
        self.splitter = self._create_splitter()
    
    def _create_splitter(self):
        """Create the appropriate text splitter based on method"""
        if self.method == "token":
            # Using sentence-transformers tokenizer for consistency with embedding model
            return SentenceTransformersTokenTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                model_name="BAAI/bge-m3"
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
                length_function=self._token_count
            )
        else:
            raise ValueError(f"Unknown chunking method: {self.method}")
    
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
        
        # Split text
        try:
            text_chunks = self.splitter.split_text(text)
        except Exception as e:
            logger.error(f"Error splitting text: {e}")
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
        
        logger.info(f"Created {len(chunks)} chunks from text")
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
                page_chunks = self.chunk_text(
                    page.text,
                    document_id,
                    metadata={
                        "page_number": page.page_number,
                        **page.metadata
                    }
                )
                all_chunks.extend(page_chunks)
        else:
            # Combine all pages and chunk together
            combined_text = "\n\n".join(page.text for page in pages)
            
            # Track page boundaries
            page_boundaries = self._calculate_page_boundaries(pages)
            
            chunks = self.chunk_text(combined_text, document_id)
            
            # Add page information to chunks
            for chunk in chunks:
                start_pos = combined_text.index(chunk.text)
                page_nums = self._get_pages_for_position(start_pos, page_boundaries)
                chunk.metadata["page_numbers"] = page_nums
                all_chunks.append(chunk)
        
        # Re-index chunks
        for i, chunk in enumerate(all_chunks):
            chunk.chunk_index = i
            chunk.chunk_id = f"chunk_{document_id}_{i:04d}_{hashlib.md5(chunk.text.encode()).hexdigest()[:16]}"
        
        return all_chunks
    
    def _token_count(self, text: str) -> int:
        """Estimate token count (simple approximation)"""
        # Rough approximation: 1 token H 4 characters
        # For more accuracy, use tiktoken or the actual tokenizer
        return len(text) // 4
    
    def _simple_split(self, text: str) -> List[str]:
        """Simple fallback text splitting"""
        chunks = []
        sentences = re.split(r'[.!?]\s+', text)
        
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _calculate_page_boundaries(self, pages: List[Any]) -> List[tuple]:
        """Calculate character positions for page boundaries"""
        boundaries = []
        current_pos = 0
        
        for page in pages:
            page_length = len(page.text)
            boundaries.append((current_pos, current_pos + page_length, page.page_number))
            current_pos += page_length + 2  # Account for \n\n separator
        
        return boundaries
    
    def _get_pages_for_position(self, position: int, boundaries: List[tuple]) -> List[int]:
        """Get page numbers for a given text position"""
        pages = []
        for start, end, page_num in boundaries:
            if start <= position < end:
                pages.append(page_num)
        return pages if pages else [1]  # Default to page 1 if not found


class SemanticChunker:
    """Advanced semantic-based text chunking"""
    
    def __init__(self, max_chunk_size: int = 512):
        self.max_chunk_size = max_chunk_size
    
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
        # Detect paragraphs
        paragraphs = self._detect_paragraphs(text)
        
        # Group paragraphs into semantic chunks
        semantic_groups = self._group_paragraphs(paragraphs)
        
        # Create chunks
        chunks = []
        for i, group in enumerate(semantic_groups):
            chunk_text = "\n\n".join(group)
            chunk_hash = hashlib.md5(chunk_text.encode()).hexdigest()[:16]
            chunk_id = f"chunk_{document_id}_{i:04d}_{chunk_hash}"
            
            chunk_metadata = {
                "document_id": document_id,
                "chunk_index": i,
                "chunk_method": "semantic",
                "paragraph_count": len(group)
            }
            
            if metadata:
                chunk_metadata.update(metadata)
            
            chunks.append(Chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=i,
                text=chunk_text,
                metadata=chunk_metadata,
                token_count=len(chunk_text) // 4,
                char_count=len(chunk_text)
            ))
        
        return chunks
    
    def _detect_paragraphs(self, text: str) -> List[str]:
        """Detect paragraph boundaries in text"""
        # Split by double newlines or indentation patterns
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Filter out empty paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        return paragraphs
    
    def _group_paragraphs(self, paragraphs: List[str]) -> List[List[str]]:
        """Group paragraphs into semantic chunks"""
        groups = []
        current_group = []
        current_size = 0
        
        for paragraph in paragraphs:
            para_size = len(paragraph)
            
            # Check if adding this paragraph would exceed max size
            if current_size + para_size > self.max_chunk_size * 4:  # Approximate tokens
                if current_group:
                    groups.append(current_group)
                current_group = [paragraph]
                current_size = para_size
            else:
                current_group.append(paragraph)
                current_size += para_size
        
        if current_group:
            groups.append(current_group)
        
        return groups


class DocumentBasedChunker:
    """Document-based chunking that preserves document structure"""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
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
            page_text = page.text
            page_metadata = {
                "page_number": page.page_number,
                "document_structure": "page_based",
                **page.metadata
            }
            
            if metadata:
                page_metadata.update(metadata)
            
            # Split page into smaller chunks if needed
            if len(page_text) > self.chunk_size * 4:  # Rough token estimate
                # Split by paragraphs first
                paragraphs = self._split_by_paragraphs(page_text)
                
                current_chunk = ""
                for paragraph in paragraphs:
                    if len(current_chunk) + len(paragraph) <= self.chunk_size * 4:
                        current_chunk += paragraph + "\n\n"
                    else:
                        if current_chunk:
                            chunk = self._create_chunk(
                                current_chunk.strip(),
                                document_id,
                                chunk_index,
                                page_metadata
                            )
                            chunks.append(chunk)
                            chunk_index += 1
                        current_chunk = paragraph + "\n\n"
                
                # Add remaining chunk
                if current_chunk:
                    chunk = self._create_chunk(
                        current_chunk.strip(),
                        document_id,
                        chunk_index,
                        page_metadata
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            else:
                # Page is small enough, use as single chunk
                chunk = self._create_chunk(
                    page_text,
                    document_id,
                    chunk_index,
                    page_metadata
                )
                chunks.append(chunk)
                chunk_index += 1
        
        return chunks
    
    def _split_by_paragraphs(self, text: str) -> List[str]:
        """Split text by paragraphs"""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _create_chunk(
        self,
        text: str,
        document_id: str,
        chunk_index: int,
        metadata: Dict[str, Any]
    ) -> Chunk:
        """Create a chunk object"""
        chunk_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        chunk_id = f"chunk_{document_id}_{chunk_index:04d}_{chunk_hash}"
        
        chunk_metadata = {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "chunk_method": "document_based",
            **metadata
        }
        
        return Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=chunk_index,
            text=text,
            metadata=chunk_metadata,
            token_count=len(text) // 4,  # Rough estimate
            char_count=len(text)
        )


class HybridChunker:
    """Hybrid approach combining multiple chunking strategies"""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ):
        self.token_chunker = TextChunker(chunk_size, chunk_overlap, "token")
        self.semantic_chunker = SemanticChunker(chunk_size)
        self.document_chunker = DocumentBasedChunker(chunk_size, chunk_overlap)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        strategy: str = "auto"
    ) -> List[Chunk]:
        """
        Apply hybrid chunking strategy
        
        Args:
            text: Text to chunk
            document_id: Document identifier
            metadata: Optional metadata
            strategy: Chunking strategy ("auto", "token", "semantic")
        
        Returns:
            List of Chunk objects
        """
        if strategy == "auto":
            # Determine best strategy based on text characteristics
            if self._is_structured_text(text):
                return self.semantic_chunker.chunk_text(text, document_id, metadata)
            else:
                return self.token_chunker.chunk_text(text, document_id, metadata)
        elif strategy == "token":
            return self.token_chunker.chunk_text(text, document_id, metadata)
        elif strategy == "semantic":
            return self.semantic_chunker.chunk_text(text, document_id, metadata)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    def _is_structured_text(self, text: str) -> bool:
        """Determine if text has clear structure (paragraphs, sections)"""
        # Check for presence of structural elements
        double_newlines = len(re.findall(r'\n\s*\n', text))
        total_lines = text.count('\n')
        
        # If there are many paragraph breaks relative to total lines
        if total_lines > 0 and double_newlines / total_lines > 0.1:
            return True
        
        # Check for section headers (lines that might be titles)
        potential_headers = re.findall(r'^[A-Z][^.!?]*$', text, re.MULTILINE)
        if len(potential_headers) > 3:
            return True
        
        return False


# Lazy loading chunker instances to avoid import-time dependencies
def get_default_chunker():
    return TextChunker()

def get_text_chunker(chunk_size=512, chunk_overlap=50, method="token"):
    return TextChunker(chunk_size, chunk_overlap, method)

def get_document_chunker(chunk_size=512, chunk_overlap=50):
    """Factory function to create DocumentBasedChunker instances"""
    return DocumentBasedChunker(chunk_size, chunk_overlap)
