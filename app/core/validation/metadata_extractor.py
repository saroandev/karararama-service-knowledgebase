"""
Document metadata extraction module
"""
import io
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import fitz as pymupdf
from fitz import Document

from schemas.validation import DocumentMetadata, DocumentType
from app.core.validation.utils import generate_document_hash

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extract metadata from documents"""

    def extract(
        self,
        file_data: bytes,
        filename: str,
        document_type: DocumentType
    ) -> DocumentMetadata:
        """
        Extract metadata from document

        Args:
            file_data: File content as bytes
            filename: Name of the file
            document_type: Type of document

        Returns:
            DocumentMetadata object
        """
        # Generate hash values
        _, md5_hash, sha256_hash = generate_document_hash(file_data)

        # Create base metadata
        metadata = DocumentMetadata(
            file_name=filename,
            file_size=len(file_data),
            md5_hash=md5_hash,
            sha256_hash=sha256_hash,
            uploaded_at=datetime.now()
        )

        # Extract type-specific metadata
        if document_type == DocumentType.PDF:
            pdf_metadata = self._extract_pdf_metadata(file_data)
            metadata = self._merge_metadata(metadata, pdf_metadata)
        elif document_type == DocumentType.TXT:
            txt_metadata = self._extract_text_metadata(file_data)
            metadata = self._merge_metadata(metadata, txt_metadata)
        # Add more document type handlers as needed

        return metadata

    def _extract_pdf_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract metadata from PDF file

        Args:
            file_data: PDF file bytes

        Returns:
            Dictionary with PDF metadata
        """
        metadata = {}

        try:
            # Open PDF from bytes
            pdf_stream = io.BytesIO(file_data)
            doc: Document = pymupdf.open(stream=pdf_stream, filetype="pdf")

            # Extract document metadata
            pdf_meta = doc.metadata

            # Map PDF metadata to our schema
            metadata['title'] = pdf_meta.get('title', '').strip() or None
            metadata['author'] = pdf_meta.get('author', '').strip() or None
            metadata['subject'] = pdf_meta.get('subject', '').strip() or None
            metadata['keywords'] = pdf_meta.get('keywords', '').strip() or None
            metadata['creator'] = pdf_meta.get('creator', '').strip() or None
            metadata['producer'] = pdf_meta.get('producer', '').strip() or None
            metadata['page_count'] = len(doc)

            # Parse dates
            if pdf_meta.get('creationDate'):
                metadata['created_at'] = self._parse_pdf_date(pdf_meta['creationDate'])
            if pdf_meta.get('modDate'):
                metadata['modified_at'] = self._parse_pdf_date(pdf_meta['modDate'])

            # Detect language (basic detection from first page)
            if len(doc) > 0:
                first_page_text = doc[0].get_text()[:1000]
                metadata['language'] = self._detect_language(first_page_text)

            # Detect encoding
            metadata['encoding'] = pdf_meta.get('encoding', 'utf-8')

            doc.close()

            logger.info(f"Extracted PDF metadata: {metadata.get('title', 'No title')}, {metadata.get('page_count', 0)} pages")

        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {e}")

        return metadata

    def _extract_text_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract metadata from text file

        Args:
            file_data: Text file bytes

        Returns:
            Dictionary with text metadata
        """
        metadata = {}

        try:
            # Detect encoding
            encodings = ['utf-8', 'latin-1', 'windows-1254', 'iso-8859-9']
            text_content = None
            detected_encoding = 'utf-8'

            for encoding in encodings:
                try:
                    text_content = file_data.decode(encoding)
                    detected_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue

            if text_content:
                metadata['encoding'] = detected_encoding

                # Count lines (as pages for text files)
                lines = text_content.split('\n')
                metadata['page_count'] = max(1, len(lines) // 50)  # Approximate pages

                # Detect language from sample
                sample = text_content[:1000]
                metadata['language'] = self._detect_language(sample)

                # Extract title from first non-empty line
                for line in lines:
                    if line.strip():
                        metadata['title'] = line.strip()[:100]  # First 100 chars as title
                        break

        except Exception as e:
            logger.error(f"Error extracting text metadata: {e}")

        return metadata

    def _parse_pdf_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse PDF date string to datetime

        Args:
            date_str: PDF date string (format: D:YYYYMMDDHHmmSS)

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None

        # Remove 'D:' prefix if present
        if date_str.startswith('D:'):
            date_str = date_str[2:]

        try:
            # Parse basic format
            year = int(date_str[0:4])
            month = int(date_str[4:6]) if len(date_str) > 4 else 1
            day = int(date_str[6:8]) if len(date_str) > 6 else 1
            hour = int(date_str[8:10]) if len(date_str) > 8 else 0
            minute = int(date_str[10:12]) if len(date_str) > 10 else 0
            second = int(date_str[12:14]) if len(date_str) > 12 else 0

            return datetime(year, month, day, hour, minute, second)
        except (ValueError, IndexError):
            logger.debug(f"Could not parse PDF date: {date_str}")
            return None

    def _detect_language(self, text_sample: str) -> str:
        """
        Detect language from text sample (basic detection)

        Args:
            text_sample: Sample text for language detection

        Returns:
            Detected language code (tr, en, etc.)
        """
        if not text_sample:
            return "unknown"

        # Turkish character indicators
        turkish_chars = 'çğıöşüÇĞİÖŞÜ'
        turkish_words = ['ve', 'ile', 'için', 'bir', 'bu', 'olan', 'olarak', 'değil']

        # Count Turkish indicators
        turkish_char_count = sum(1 for char in text_sample if char in turkish_chars)
        turkish_word_count = sum(1 for word in turkish_words if word in text_sample.lower())

        # Basic detection logic
        if turkish_char_count > 5 or turkish_word_count > 3:
            return "tr"

        # English indicators
        english_words = ['the', 'and', 'for', 'with', 'this', 'that', 'from', 'have']
        english_word_count = sum(1 for word in english_words if word in text_sample.lower())

        if english_word_count > 3:
            return "en"

        return "unknown"

    def _merge_metadata(
        self,
        base: DocumentMetadata,
        extracted: Dict[str, Any]
    ) -> DocumentMetadata:
        """
        Merge extracted metadata into base metadata

        Args:
            base: Base metadata object
            extracted: Extracted metadata dictionary

        Returns:
            Merged DocumentMetadata object
        """
        # Update base metadata with extracted values
        for key, value in extracted.items():
            if value is not None and hasattr(base, key):
                setattr(base, key, value)

        return base

    def get_metadata_quality_score(self, metadata: DocumentMetadata) -> float:
        """
        Calculate metadata quality score

        Args:
            metadata: DocumentMetadata object

        Returns:
            Quality score between 0 and 1
        """
        score = 0.0
        total_fields = 0

        # Check important fields
        important_fields = ['title', 'author', 'page_count', 'created_at', 'language']
        for field in important_fields:
            total_fields += 1
            value = getattr(metadata, field, None)
            if value and (not isinstance(value, str) or value.strip()):
                score += 1.0

        # Check optional fields (less weight)
        optional_fields = ['subject', 'keywords', 'creator', 'producer']
        for field in optional_fields:
            total_fields += 0.5  # Half weight
            value = getattr(metadata, field, None)
            if value and (not isinstance(value, str) or value.strip()):
                score += 0.5

        return score / total_fields if total_fields > 0 else 0.0