"""
Document type detection module
"""
import logging
from typing import Optional, Dict, Any

from schemas.validation import DocumentType
from app.core.validation.utils import (
    check_magic_bytes,
    detect_mime_type,
    get_file_extension
)

logger = logging.getLogger(__name__)


class DocumentTypeDetector:
    """Detect document type from file data and metadata"""

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        'pdf': DocumentType.PDF,
        'docx': DocumentType.DOCX,
        'doc': DocumentType.DOCX,
        'txt': DocumentType.TXT,
        'text': DocumentType.TXT,
        'html': DocumentType.HTML,
        'htm': DocumentType.HTML,
        'md': DocumentType.MARKDOWN,
        'markdown': DocumentType.MARKDOWN
    }

    # MIME type mappings
    MIME_TYPE_MAPPINGS = {
        'application/pdf': DocumentType.PDF,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DocumentType.DOCX,
        'application/msword': DocumentType.DOCX,
        'text/plain': DocumentType.TXT,
        'text/html': DocumentType.HTML,
        'text/markdown': DocumentType.MARKDOWN,
        'text/x-markdown': DocumentType.MARKDOWN
    }

    def detect(
        self,
        file_data: bytes,
        filename: str,
        mime_type: Optional[str] = None
    ) -> tuple[DocumentType, Dict[str, Any]]:
        """
        Detect document type from multiple sources

        Args:
            file_data: File content as bytes
            filename: Name of the file
            mime_type: Optional MIME type hint

        Returns:
            Tuple of (DocumentType, detection_info)
        """
        detection_info = {
            "filename": filename,
            "file_size": len(file_data),
            "detection_methods": []
        }

        # Method 1: Check magic bytes
        magic_results = check_magic_bytes(file_data)
        document_type = self._detect_from_magic_bytes(magic_results)
        if document_type != DocumentType.UNKNOWN:
            detection_info["detection_methods"].append("magic_bytes")
            detection_info["magic_bytes_result"] = magic_results
            logger.info(f"Document type detected via magic bytes: {document_type}")
            return document_type, detection_info

        # Method 2: Check file extension
        extension = get_file_extension(filename)
        if extension in self.SUPPORTED_EXTENSIONS:
            document_type = self.SUPPORTED_EXTENSIONS[extension]
            detection_info["detection_methods"].append("file_extension")
            detection_info["file_extension"] = extension
            logger.info(f"Document type detected via extension: {document_type}")
            return document_type, detection_info

        # Method 3: Check MIME type
        if not mime_type:
            mime_type = detect_mime_type(filename)

        if mime_type and mime_type in self.MIME_TYPE_MAPPINGS:
            document_type = self.MIME_TYPE_MAPPINGS[mime_type]
            detection_info["detection_methods"].append("mime_type")
            detection_info["mime_type"] = mime_type
            logger.info(f"Document type detected via MIME type: {document_type}")
            return document_type, detection_info

        # Method 4: Content-based detection (fallback)
        document_type = self._detect_from_content(file_data)
        if document_type != DocumentType.UNKNOWN:
            detection_info["detection_methods"].append("content_analysis")
            logger.info(f"Document type detected via content analysis: {document_type}")
            return document_type, detection_info

        # Could not detect type
        logger.warning(f"Could not detect document type for: {filename}")
        detection_info["detection_methods"].append("failed")
        return DocumentType.UNKNOWN, detection_info

    def _detect_from_magic_bytes(self, magic_results: Dict[str, bool]) -> DocumentType:
        """
        Detect document type from magic bytes results

        Args:
            magic_results: Dictionary with magic byte check results

        Returns:
            Detected DocumentType
        """
        if magic_results.get("is_pdf"):
            return DocumentType.PDF
        elif magic_results.get("is_docx"):
            return DocumentType.DOCX
        elif magic_results.get("is_html"):
            return DocumentType.HTML
        elif magic_results.get("is_txt"):
            return DocumentType.TXT
        return DocumentType.UNKNOWN

    def _detect_from_content(self, file_data: bytes) -> DocumentType:
        """
        Detect document type from content analysis

        Args:
            file_data: File content as bytes

        Returns:
            Detected DocumentType
        """
        try:
            # Try to decode as text
            text_sample = file_data[:2048].decode('utf-8', errors='ignore')

            # Check for markdown indicators
            markdown_indicators = ['# ', '## ', '```', '[](', '![](', '**', '__', '- [ ]', '- [x]']
            markdown_count = sum(1 for indicator in markdown_indicators if indicator in text_sample)
            if markdown_count >= 2:
                return DocumentType.MARKDOWN

            # Check for HTML
            if '<html' in text_sample.lower() or '<!doctype' in text_sample.lower():
                return DocumentType.HTML

            # If it's decodable and not other formats, it's likely plain text
            if len(text_sample) > 100:
                return DocumentType.TXT

        except Exception as e:
            logger.debug(f"Content detection error: {e}")

        return DocumentType.UNKNOWN

    def is_supported(self, document_type: DocumentType) -> bool:
        """
        Check if document type is supported for processing

        Args:
            document_type: Document type to check

        Returns:
            True if supported, False otherwise
        """
        return document_type != DocumentType.UNKNOWN

    def get_processing_hints(self, document_type: DocumentType) -> Dict[str, Any]:
        """
        Get processing hints based on document type

        Args:
            document_type: Type of document

        Returns:
            Dictionary with processing hints
        """
        hints = {
            DocumentType.PDF: {
                "parser": "PDFParser",
                "extract_images": True,
                "extract_tables": True,
                "preserve_layout": False,
                "ocr_fallback": True
            },
            DocumentType.DOCX: {
                "parser": "DOCXParser",
                "extract_images": True,
                "extract_tables": True,
                "preserve_layout": False,
                "ocr_fallback": False
            },
            DocumentType.TXT: {
                "parser": "TextParser",
                "extract_images": False,
                "extract_tables": False,
                "preserve_layout": False,
                "ocr_fallback": False
            },
            DocumentType.HTML: {
                "parser": "HTMLParser",
                "extract_images": True,
                "extract_tables": True,
                "preserve_layout": False,
                "ocr_fallback": False
            },
            DocumentType.MARKDOWN: {
                "parser": "MarkdownParser",
                "extract_images": False,
                "extract_tables": True,
                "preserve_layout": True,
                "ocr_fallback": False
            }
        }

        return hints.get(document_type, {
            "parser": "GenericParser",
            "extract_images": False,
            "extract_tables": False,
            "preserve_layout": False,
            "ocr_fallback": False
        })