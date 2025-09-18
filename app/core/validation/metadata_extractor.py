"""
Document metadata extraction module
"""
import io
import logging
import re
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

            # If still no title after PDF extraction, use cleaned filename
            if not metadata.title:
                metadata.title = self._clean_filename_as_title(filename)
                logger.info(f"Using cleaned filename as title: {metadata.title}")
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

            # Extract and validate title
            pdf_title = pdf_meta.get('title', '').strip() or None
            validated_title = self._validate_and_clean_title(pdf_title)

            # If invalid, try extracting from content
            if not validated_title:
                validated_title = self._extract_title_from_content(doc)
                if validated_title:
                    logger.info(f"Extracted title from content: {validated_title[:50]}...")

            # If still no title, use cleaned filename (will be set later)
            metadata['title'] = validated_title
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

            # Log extraction result
            title_source = "metadata" if metadata.get('title') else "pending"
            logger.info(f"Extracted PDF metadata: {metadata.get('title', 'No title')} (source: {title_source}), {metadata.get('page_count', 0)} pages")

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

                # Extract title from first non-empty line(s)
                # For text documents, combine multiple lines if they form a title
                title_lines = []
                for line in lines[:5]:  # Check first 5 lines
                    stripped = line.strip()
                    if stripped and len(stripped) > 10:
                        # Check if uppercase (common for titles)
                        if stripped.isupper():
                            title_lines.append(stripped)
                            # Continue if doesn't end with sentence ending
                            if not stripped.endswith(('.', '!', '?')):
                                continue
                        elif not title_lines:  # First non-empty line as fallback
                            title_lines.append(stripped)
                        break

                if title_lines:
                    metadata['title'] = ' '.join(title_lines)  # No character limit

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

    def _validate_and_clean_title(self, title: Optional[str]) -> Optional[str]:
        """
        Validate and clean document title

        Args:
            title: Raw title from PDF metadata

        Returns:
            Validated title or None if invalid
        """
        if not title:
            return None

        # Strip whitespace
        title = title.strip()

        # Reject if title is just numbers
        if title.isdigit():
            logger.debug(f"Rejecting numeric-only title: {title}")
            return None

        # Reject very short titles (less than 3 chars)
        if len(title) < 3:
            logger.debug(f"Rejecting short title: {title}")
            return None

        # Reject common meaningless titles
        invalid_titles = [
            'untitled', 'document', 'pdf', 'file', 'doc', 'page',
            'microsoft word', 'word document', 'new document',
            '1', '2', '3', 'a', 'b', 'c', 'temp', 'tmp', 'test'
        ]
        if title.lower() in invalid_titles:
            logger.debug(f"Rejecting meaningless title: {title}")
            return None

        # Reject if title is just punctuation/special chars
        if not any(c.isalnum() for c in title):
            logger.debug(f"Rejecting non-alphanumeric title: {title}")
            return None

        # Reject if title looks like a file path
        if '/' in title or '\\' in title or title.startswith('C:'):
            logger.debug(f"Rejecting path-like title: {title}")
            return None

        return title

    def _extract_title_from_content(self, doc: Document) -> Optional[str]:
        """
        Extract title from first page content if metadata title is invalid

        Args:
            doc: PyMuPDF document object

        Returns:
            Extracted title or None
        """
        if len(doc) == 0:
            return None

        try:
            # Get first page text
            first_page = doc[0]
            text = first_page.get_text()

            # Get first few non-empty lines
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            # Check first 10 lines for potential title
            # For legal documents, titles can span multiple lines
            potential_title_lines = []
            for i, line in enumerate(lines[:10]):
                # Skip very short lines (less than 10 chars)
                if len(line) < 10:
                    continue

                # Check if it looks like a title
                if self._looks_like_title(line, i):
                    # Additional validation
                    if not line.isdigit() and any(c.isalpha() for c in line):
                        potential_title_lines.append(line.strip())

                        # For Turkish legal documents, check next lines for continuation
                        # If current line is all caps and doesn't end with sentence ending
                        if line.isupper() and not line.rstrip().endswith(('.', '!', '?')):
                            # Check next lines for continuation
                            for j in range(i + 1, min(i + 5, len(lines))):
                                next_line = lines[j].strip()
                                # If next line is also uppercase and looks like continuation
                                if next_line and next_line.isupper() and len(next_line) > 10:
                                    potential_title_lines.append(next_line)
                                else:
                                    break

                        # Combine multi-line title
                        if potential_title_lines:
                            full_title = ' '.join(potential_title_lines)
                            # Clean up the title
                            full_title = full_title.rstrip('.:;')
                            # Remove multiple spaces
                            full_title = ' '.join(full_title.split())

                            # Log multi-line title extraction
                            if len(potential_title_lines) > 1:
                                logger.info(f"Extracted multi-line title ({len(potential_title_lines)} lines): {full_title[:100]}...")

                            return full_title

                # If we found a single-line title, return it
                elif potential_title_lines:
                    break

        except Exception as e:
            logger.debug(f"Could not extract title from content: {e}")

        return None

    def _looks_like_title(self, text: str, line_index: int) -> bool:
        """
        Check if text looks like a document title

        Args:
            text: Text to check
            line_index: Position of line in document (earlier = more likely)

        Returns:
            True if text appears to be a title
        """
        # Prefer lines at the beginning
        if line_index > 5:
            return False

        # Check if all caps (common for legal documents)
        if text.isupper() and len(text.split()) > 2:
            return True

        # Check if title case
        if self._is_title_case(text):
            return True

        # Check for common title keywords (Turkish legal documents)
        title_keywords = [
            'KANUN', 'YÖNETMELİK', 'KARAR', 'GENELGE', 'TEBLİĞ',
            'ANAYASA', 'MADDE', 'HAKKINDA', 'DAİR', 'İLİŞKİN'
        ]
        text_upper = text.upper()
        if any(keyword in text_upper for keyword in title_keywords):
            return True

        return False

    def _is_title_case(self, text: str) -> bool:
        """
        Check if text appears to be in title case

        Args:
            text: Text to check

        Returns:
            True if text is in title case
        """
        words = text.split()
        if len(words) < 2:
            return False

        # Count capitalized significant words (ignore short words)
        significant_words = [w for w in words if len(w) > 3]
        if not significant_words:
            return False

        capitalized = sum(1 for word in significant_words if word[0].isupper())
        return capitalized >= len(significant_words) * 0.6  # 60% or more words capitalized

    def _clean_filename_as_title(self, filename: str) -> str:
        """
        Clean filename to use as document title

        Args:
            filename: Original filename

        Returns:
            Cleaned title from filename
        """
        # Remove extension
        title = filename.rsplit('.', 1)[0]

        # Replace underscores and hyphens with spaces
        title = title.replace('_', ' ').replace('-', ' ')

        # Remove multiple spaces
        title = ' '.join(title.split())

        # Remove common prefixes/suffixes
        prefixes_to_remove = ['doc_', 'document_', 'pdf_', 'file_', 'scan_', 'copy_']
        for prefix in prefixes_to_remove:
            if title.lower().startswith(prefix):
                title = title[len(prefix):]

        # Remove date patterns at the beginning (like 20240115_)
        import re
        title = re.sub(r'^\d{8}_', '', title)
        title = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', title)

        # Handle if title is now empty
        if not title:
            title = filename.rsplit('.', 1)[0]

        # Capitalize properly if all lowercase
        if title.islower():
            title = ' '.join(word.capitalize() for word in title.split())
        # If all uppercase and long, make it title case
        elif title.isupper() and len(title) > 20:
            title = title.title()

        return title