"""
Backward compatibility module for document parsing.

This file is kept for backward compatibility.
All imports from 'app.parse' will be redirected to the new package structure.
New code should use 'from app.core.parsing import ...' directly.
"""
import logging
import warnings
from typing import List, Dict, Any, Tuple

# Import from new location
from app.core.parsing import (
    AbstractParser,
    PageContent,
    DocumentMetadata,
    PDFParser as NewPDFParser,
    create_parser,
    default_parser
)

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "Importing from app.parse is deprecated. Use app.core.parsing instead.",
    DeprecationWarning,
    stacklevel=2
)


# Legacy PDFParser class for backward compatibility
class PDFParser:
    """
    Legacy PDFParser class for backward compatibility.
    This wraps the new PDFParser implementation.
    """

    def __init__(self):
        """Initialize PDF parser"""
        warnings.warn(
            "PDFParser from app.parse is deprecated. Use PDFParser from app.core.parsing",
            DeprecationWarning,
            stacklevel=2
        )

        self._impl = NewPDFParser()
        self.supported_formats = self._impl.supported_formats

    def extract_text_from_pdf(self, file_data: bytes) -> Tuple[List[PageContent], DocumentMetadata]:
        """
        Extract text and metadata from PDF

        Args:
            file_data: PDF file bytes

        Returns:
            Tuple of (list of PageContent, DocumentMetadata)
        """
        return self._impl.extract_text(file_data, file_type='pdf')

    def extract_text_with_layout(self, file_data: bytes) -> List[PageContent]:
        """
        Extract text while preserving layout information

        Args:
            file_data: PDF file bytes

        Returns:
            List of PageContent with layout preserved
        """
        return self._impl.extract_text_with_layout(file_data, file_type='pdf')

    def extract_images(self, file_data: bytes) -> List[Dict[str, Any]]:
        """
        Extract images from PDF

        Args:
            file_data: PDF file bytes

        Returns:
            List of image metadata
        """
        return self._impl.extract_images(file_data)

    def _extract_metadata(self, doc, file_data: bytes) -> DocumentMetadata:
        """Extract document metadata - delegates to implementation"""
        # This is called internally, delegate to new implementation
        return self._impl._extract_metadata(doc, file_data)

    def _parse_pdf_date(self, date_str: str) -> str:
        """Parse PDF date string to ISO format"""
        return self._impl._parse_pdf_date(date_str)

    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        return self._impl.clean_text(text)

    def _detect_tables(self, page) -> List[Dict[str, Any]]:
        """Detect tables in a page"""
        return self._impl._detect_tables(page)

    def _process_blocks(self, blocks: Dict[str, Any]) -> str:
        """Process text blocks to preserve structure"""
        return self._impl._process_blocks(blocks)


# Create singleton instance for backward compatibility
pdf_parser = PDFParser()


# Export everything for backward compatibility
__all__ = [
    'PageContent',
    'DocumentMetadata',
    'PDFParser',
    'pdf_parser',
    # Also export new names
    'AbstractParser',
    'create_parser',
    'default_parser'
]