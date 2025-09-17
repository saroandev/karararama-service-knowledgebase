"""
Parsing package for document text extraction

This package provides document parsing implementations:
- PDF parsing with PyMuPDF
- Extensible for other document formats
"""
import logging
from typing import Optional

from app.core.parsing.base import AbstractParser
from schemas.parsing import PageContent, DocumentMetadata
from app.core.parsing.pdf_parser import PDFParser
from app.core.parsing.utils import (
    detect_file_type,
    estimate_reading_time,
    extract_text_statistics,
    truncate_text,
    normalize_whitespace,
    extract_keywords
)

logger = logging.getLogger(__name__)


def create_parser(
    file_type: Optional[str] = None,
    **kwargs
) -> AbstractParser:
    """
    Factory function to create document parser based on file type

    Args:
        file_type: Document type ('pdf', 'docx', etc.)
        **kwargs: Additional arguments for the specific implementation

    Returns:
        Document parser instance
    """
    file_type = file_type or 'pdf'

    if file_type.lower() in ['pdf', '.pdf']:
        logger.info("Creating PDF parser")
        return PDFParser(**kwargs)
    else:
        # Default to PDF parser for now
        logger.warning(f"Unsupported file type '{file_type}', using PDF parser")
        return PDFParser(**kwargs)


# Create default parser instance (PDF)
try:
    default_parser = create_parser(file_type='pdf')
    logger.info("Default parser initialized for PDF documents")
except Exception as e:
    logger.error(f"Failed to initialize default parser: {e}")
    default_parser = None


# Export all classes and functions
__all__ = [
    # Base classes
    'AbstractParser',
    'PageContent',
    'DocumentMetadata',
    # Implementations
    'PDFParser',
    # Factory
    'create_parser',
    'default_parser',
    # Utils
    'detect_file_type',
    'estimate_reading_time',
    'extract_text_statistics',
    'truncate_text',
    'normalize_whitespace',
    'extract_keywords'
]