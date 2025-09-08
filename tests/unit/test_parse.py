"""
Unit tests for PDF parsing module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import io
from pathlib import Path

from app.parse import PDFParser, pdf_parser


@pytest.mark.unit
@pytest.mark.parse
class TestPDFParser:
    """Test the PDFParser class"""

    def test_pdf_parser_instance(self):
        """Test PDFParser instance creation"""
        parser = PDFParser()
        assert parser is not None

    @patch('app.parse.fitz')
    def test_extract_text_from_pdf_success(self, mock_fitz):
        """Test successful PDF text extraction"""
        # Mock PyMuPDF document
        mock_doc = MagicMock()
        mock_page1 = MagicMock()
        mock_page2 = MagicMock()
        
        mock_page1.get_text.return_value = "First page content"
        mock_page1.number = 0
        mock_page2.get_text.return_value = "Second page content"
        mock_page2.number = 1
        
        mock_doc.__len__.return_value = 2
        mock_doc.__iter__.return_value = iter([mock_page1, mock_page2])
        mock_doc.metadata = {"title": "Test Document", "author": "Test Author"}
        mock_doc.page_count = 2
        
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        parser = PDFParser()
        pdf_data = b"mock pdf content"
        
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        # Verify results
        assert len(pages) == 2
        assert pages[0].text == "First page content"
        assert pages[0].page_number == 1  # 1-indexed
        assert pages[1].text == "Second page content" 
        assert pages[1].page_number == 2
        
        assert metadata.title == "Test Document"
        assert metadata.file_size == len(pdf_data)
        assert metadata.page_count == 2

    @patch('app.parse.fitz')
    def test_extract_text_from_pdf_empty_document(self, mock_fitz):
        """Test PDF extraction from empty document"""
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 0
        mock_doc.__iter__.return_value = iter([])
        mock_doc.metadata = {}
        mock_doc.page_count = 0
        
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        parser = PDFParser()
        pdf_data = b"empty pdf"
        
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        assert len(pages) == 0
        assert metadata.page_count == 0
        assert metadata.file_size == len(pdf_data)

    @patch('app.parse.fitz')
    def test_extract_text_from_pdf_with_errors(self, mock_fitz):
        """Test PDF extraction with page processing errors"""
        mock_doc = MagicMock()
        mock_page1 = MagicMock()
        mock_page2 = MagicMock()
        
        # First page works fine
        mock_page1.get_text.return_value = "First page content"
        mock_page1.number = 0
        
        # Second page throws an exception
        mock_page2.get_text.side_effect = Exception("Page processing error")
        mock_page2.number = 1
        
        mock_doc.__len__.return_value = 2
        mock_doc.__iter__.return_value = iter([mock_page1, mock_page2])
        mock_doc.metadata = {"title": "Test Document"}
        mock_doc.page_count = 2
        
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        parser = PDFParser()
        pdf_data = b"problematic pdf content"
        
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        # Should still return the successful page
        assert len(pages) == 1
        assert pages[0].text == "First page content"
        assert metadata.page_count == 2  # Original count

    @patch('app.parse.fitz')
    def test_extract_text_from_pdf_file_error(self, mock_fitz):
        """Test PDF extraction when file cannot be opened"""
        mock_fitz.open.side_effect = Exception("Cannot open PDF file")
        
        parser = PDFParser()
        pdf_data = b"corrupted pdf"
        
        with pytest.raises(Exception, match="Cannot open PDF file"):
            parser.extract_text_from_pdf(pdf_data)

    @patch('app.parse.fitz')
    def test_extract_text_preserves_whitespace(self, mock_fitz):
        """Test that text extraction preserves important whitespace"""
        mock_doc = MagicMock()
        mock_page = MagicMock()
        
        mock_page.get_text.return_value = "Line 1\n\nLine 2\n   Indented line"
        mock_page.number = 0
        
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_doc.metadata = {}
        mock_doc.page_count = 1
        
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        parser = PDFParser()
        pdf_data = b"pdf with formatting"
        
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        assert pages[0].text == "Line 1\n\nLine 2\n   Indented line"

    @patch('app.parse.fitz')
    def test_metadata_extraction(self, mock_fitz):
        """Test comprehensive metadata extraction"""
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 0
        mock_doc.__iter__.return_value = iter([])
        mock_doc.metadata = {
            "title": "Complete Test Document",
            "author": "John Doe", 
            "subject": "Test Subject",
            "creator": "Test Creator",
            "producer": "Test Producer",
            "creationDate": "D:20240101120000",
            "modDate": "D:20240101120000"
        }
        mock_doc.page_count = 5
        
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        parser = PDFParser()
        pdf_data = b"pdf with rich metadata"
        
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        assert metadata.title == "Complete Test Document"
        assert metadata.author == "John Doe"
        assert metadata.subject == "Test Subject"
        assert metadata.creator == "Test Creator"
        assert metadata.producer == "Test Producer"
        assert metadata.page_count == 5
        assert metadata.file_size == len(pdf_data)

    def test_page_data_structure(self):
        """Test PageData structure"""
        from app.parse import PageData
        
        page = PageData(
            text="Sample text",
            page_number=1,
            metadata={"key": "value"}
        )
        
        assert page.text == "Sample text"
        assert page.page_number == 1
        assert page.metadata == {"key": "value"}

    def test_document_metadata_structure(self):
        """Test DocumentMetadata structure"""
        from app.parse import DocumentMetadata
        
        metadata = DocumentMetadata(
            title="Test Title",
            author="Test Author",
            subject="Test Subject",
            creator="Test Creator", 
            producer="Test Producer",
            file_size=1024,
            page_count=5
        )
        
        assert metadata.title == "Test Title"
        assert metadata.author == "Test Author"
        assert metadata.subject == "Test Subject"
        assert metadata.creator == "Test Creator"
        assert metadata.producer == "Test Producer"
        assert metadata.file_size == 1024
        assert metadata.page_count == 5

    def test_singleton_pdf_parser(self):
        """Test that pdf_parser is properly instantiated"""
        from app.parse import pdf_parser
        assert isinstance(pdf_parser, PDFParser)

    @patch('app.parse.fitz')
    def test_large_document_handling(self, mock_fitz):
        """Test handling of documents with many pages"""
        mock_doc = MagicMock()
        
        # Create 100 mock pages
        mock_pages = []
        for i in range(100):
            mock_page = MagicMock()
            mock_page.get_text.return_value = f"Page {i+1} content"
            mock_page.number = i
            mock_pages.append(mock_page)
        
        mock_doc.__len__.return_value = 100
        mock_doc.__iter__.return_value = iter(mock_pages)
        mock_doc.metadata = {"title": "Large Document"}
        mock_doc.page_count = 100
        
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        parser = PDFParser()
        pdf_data = b"large pdf content"
        
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        assert len(pages) == 100
        assert pages[0].text == "Page 1 content"
        assert pages[99].text == "Page 100 content"
        assert metadata.page_count == 100

    @patch('app.parse.fitz')
    def test_unicode_content_handling(self, mock_fitz):
        """Test handling of Unicode content in PDFs"""
        mock_doc = MagicMock()
        mock_page = MagicMock()
        
        # Unicode content with various characters
        unicode_text = "Testing Unicode: é, ñ, ü, 中文, العربية, 🚀"
        mock_page.get_text.return_value = unicode_text
        mock_page.number = 0
        
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_doc.metadata = {"title": "Unicode Document"}
        mock_doc.page_count = 1
        
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        parser = PDFParser()
        pdf_data = "unicode pdf content".encode('utf-8')
        
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        assert pages[0].text == unicode_text
        assert metadata.title == "Unicode Document"