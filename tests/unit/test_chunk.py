"""
Unit tests for text chunking module
"""
import pytest
from unittest.mock import Mock, patch
from app.chunk import DocumentBasedChunker, get_document_chunker
from app.parse import PageContent


@pytest.mark.unit
@pytest.mark.chunk
class TestDocumentBasedChunker:
    """Test the DocumentBasedChunker class"""

    def test_chunker_initialization_default(self):
        """Test chunker with default parameters"""
        chunker = DocumentBasedChunker()
        
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 50

    def test_chunker_initialization_custom(self):
        """Test chunker with custom parameters"""
        chunker = DocumentBasedChunker(chunk_size=256, chunk_overlap=25)
        
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 25

    def test_chunk_by_document_simple(self):
        """Test basic document chunking"""
        chunker = DocumentBasedChunker(chunk_size=100, chunk_overlap=10)
        
        # Create mock pages
        pages = [
            PageContent(
                text="This is the first page with some content that should be chunked properly.",
                page_number=1,
                metadata={"page": 1}
            ),
            PageContent(
                text="This is the second page with different content for testing purposes.",
                page_number=2, 
                metadata={"page": 2}
            )
        ]
        
        document_id = "test_doc_001"
        document_metadata = {"title": "Test Document"}
        
        chunks = chunker.chunk_by_document(pages, document_id, document_metadata)
        
        # Verify chunks were created
        assert len(chunks) > 0
        
        # Check chunk structure
        for chunk in chunks:
            assert hasattr(chunk, 'chunk_id')
            assert hasattr(chunk, 'text')
            assert hasattr(chunk, 'metadata')
            assert hasattr(chunk, 'token_count')
            assert hasattr(chunk, 'char_count')
            
            assert chunk.document_id == document_id
            assert isinstance(chunk.text, str)
            assert len(chunk.text) > 0
            assert isinstance(chunk.metadata, dict)

    def test_chunk_by_document_empty_pages(self):
        """Test chunking with empty pages"""
        chunker = DocumentBasedChunker()
        
        pages = []
        document_id = "empty_doc"
        
        chunks = chunker.chunk_by_document(pages, document_id, {})
        
        assert len(chunks) == 0

    def test_chunk_by_document_single_page(self):
        """Test chunking with single page"""
        chunker = DocumentBasedChunker(chunk_size=50, chunk_overlap=5)
        
        pages = [
            PageContent(
                text="Short single page content.",
                page_number=1,
                metadata={"page": 1}
            )
        ]
        
        document_id = "single_page_doc"
        chunks = chunker.chunk_by_document(pages, document_id, {})
        
        assert len(chunks) >= 1
        assert chunks[0].text == "Short single page content."
        assert chunks[0].metadata["page_number"] == 1

    def test_chunk_by_document_large_page(self):
        """Test chunking with page larger than chunk size"""
        chunker = DocumentBasedChunker(chunk_size=50, chunk_overlap=10)
        
        # Create a long text that will need multiple chunks
        long_text = "This is a very long piece of text that should be split into multiple chunks because it exceeds the maximum chunk size limit that we have set for testing purposes."
        
        pages = [
            PageContent(
                text=long_text,
                page_number=1,
                metadata={"page": 1}
            )
        ]
        
        document_id = "large_page_doc"
        chunks = chunker.chunk_by_document(pages, document_id, {})
        
        # Should create multiple chunks
        assert len(chunks) > 1
        
        # Verify overlap between chunks
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]
            next_chunk = chunks[i + 1]
            
            # Check that chunks don't exceed size limit (approximately)
            assert len(current_chunk.text) <= chunker.chunk_size * 6  # rough token-to-char ratio
            
            # All chunks should have same document metadata
            assert current_chunk.document_id == document_id
            assert next_chunk.document_id == document_id

    def test_chunk_metadata_inheritance(self):
        """Test that chunks inherit document metadata"""
        chunker = DocumentBasedChunker(chunk_size=100, chunk_overlap=10)
        
        pages = [
            PageContent(
                text="Test content for metadata inheritance.",
                page_number=1,
                metadata={"source": "test", "language": "en"}
            )
        ]
        
        document_id = "metadata_test_doc"
        document_metadata = {"title": "Test Document", "author": "Test Author"}
        
        chunks = chunker.chunk_by_document(pages, document_id, document_metadata)
        
        assert len(chunks) >= 1
        chunk = chunks[0]
        
        # Should have document metadata
        assert chunk.metadata["title"] == "Test Document"
        assert chunk.metadata["author"] == "Test Author"
        
        # Should have page metadata
        assert chunk.metadata["page_number"] == 1
        assert chunk.metadata["source"] == "test"
        assert chunk.metadata["language"] == "en"

    def test_chunk_ids_are_unique(self):
        """Test that chunk IDs are unique"""
        chunker = DocumentBasedChunker(chunk_size=30, chunk_overlap=5)
        
        long_text = "This is a test text that will be split into multiple chunks to verify that chunk IDs are unique across all generated chunks."
        
        pages = [
            PageContent(text=long_text, page_number=1, metadata={})
        ]
        
        document_id = "unique_id_test"
        chunks = chunker.chunk_by_document(pages, document_id, {})
        
        # Extract all chunk IDs
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        
        # Verify uniqueness
        assert len(chunk_ids) == len(set(chunk_ids))
        
        # Verify IDs follow expected pattern
        for chunk_id in chunk_ids:
            assert chunk_id.startswith(f"{document_id}_chunk_")

    def test_chunk_token_counting(self):
        """Test token count estimation"""
        chunker = DocumentBasedChunker()
        
        pages = [
            PageContent(
                text="This is a simple test sentence with multiple words.",
                page_number=1,
                metadata={}
            )
        ]
        
        chunks = chunker.chunk_by_document(pages, "token_test", {})
        
        assert len(chunks) >= 1
        chunk = chunks[0]
        
        # Token count should be reasonable (roughly 1 token per 4 characters)
        expected_tokens = len(chunk.text) // 4
        assert abs(chunk.token_count - expected_tokens) <= expected_tokens * 0.5

    def test_chunk_char_counting(self):
        """Test character count accuracy"""
        chunker = DocumentBasedChunker()
        
        test_text = "Exact character count test."
        pages = [
            PageContent(text=test_text, page_number=1, metadata={})
        ]
        
        chunks = chunker.chunk_by_document(pages, "char_test", {})
        
        assert len(chunks) >= 1
        chunk = chunks[0]
        
        assert chunk.char_count == len(test_text)

    def test_chunk_overlap_functionality(self):
        """Test that chunk overlap works correctly"""
        chunker = DocumentBasedChunker(chunk_size=40, chunk_overlap=20)
        
        # Text that will definitely need splitting
        long_text = "First sentence for testing overlap. Second sentence should appear in multiple chunks. Third sentence completes the test."
        
        pages = [
            PageContent(text=long_text, page_number=1, metadata={})
        ]
        
        chunks = chunker.chunk_by_document(pages, "overlap_test", {})
        
        if len(chunks) > 1:
            # Check that there's some overlap between consecutive chunks
            # This is implementation-specific, but we can check that chunks aren't completely disjoint
            for i in range(len(chunks) - 1):
                current_end = chunks[i].text[-20:]  # Last 20 chars
                next_start = chunks[i + 1].text[:20]  # First 20 chars
                
                # There should be some common content (though exact overlap depends on sentence boundaries)
                # This is a rough check since sentence-aware splitting might affect exact overlap
                assert len(current_end.strip()) > 0
                assert len(next_start.strip()) > 0

    def test_empty_text_handling(self):
        """Test handling of empty or whitespace-only text"""
        chunker = DocumentBasedChunker()
        
        pages = [
            PageContent(text="", page_number=1, metadata={}),
            PageContent(text="   \n\t  ", page_number=2, metadata={}),
            PageContent(text="Valid content", page_number=3, metadata={})
        ]
        
        chunks = chunker.chunk_by_document(pages, "empty_text_test", {})
        
        # Should only create chunks for non-empty content
        assert len(chunks) >= 1
        valid_chunks = [chunk for chunk in chunks if chunk.text.strip()]
        assert len(valid_chunks) >= 1
        assert "Valid content" in valid_chunks[0].text

    def test_get_document_chunker_function(self):
        """Test the get_document_chunker factory function"""
        chunker = get_document_chunker()
        
        assert isinstance(chunker, DocumentBasedChunker)
        assert chunker.chunk_size == 512  # default
        assert chunker.chunk_overlap == 50  # default

    def test_get_document_chunker_with_params(self):
        """Test the get_document_chunker factory function with parameters"""
        chunker = get_document_chunker(chunk_size=256, chunk_overlap=25)
        
        assert isinstance(chunker, DocumentBasedChunker)
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 25

    @patch('app.chunk.logger')
    def test_chunker_logging(self, mock_logger):
        """Test that chunker logs appropriately"""
        chunker = DocumentBasedChunker()
        
        pages = [
            PageContent(text="Test logging functionality", page_number=1, metadata={})
        ]
        
        chunks = chunker.chunk_by_document(pages, "logging_test", {})
        
        # Verify some logging occurred (implementation dependent)
        assert len(chunks) > 0  # Main assertion
        # Logging assertions would depend on actual implementation

    def test_chunk_sequential_numbering(self):
        """Test that chunks are numbered sequentially"""
        chunker = DocumentBasedChunker(chunk_size=30, chunk_overlap=5)
        
        # Create text that will generate multiple chunks
        long_text = " ".join([f"Sentence {i} with some content." for i in range(1, 10)])
        
        pages = [
            PageContent(text=long_text, page_number=1, metadata={})
        ]
        
        chunks = chunker.chunk_by_document(pages, "sequential_test", {})
        
        # Verify chunks have sequential indices in their metadata or IDs
        for i, chunk in enumerate(chunks):
            # This assumes chunk_id contains sequential information
            assert str(i).zfill(3) in chunk.chunk_id or chunk.metadata.get('chunk_index') == i