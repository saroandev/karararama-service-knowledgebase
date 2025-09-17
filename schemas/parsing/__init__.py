"""
Parsing schemas for document processing
"""
from schemas.parsing.page import PageContent
from schemas.parsing.document import DocumentMetadata, DocumentProcessingResult

__all__ = [
    'PageContent',
    'DocumentMetadata',
    'DocumentProcessingResult'
]