"""
Document content analysis module
"""
import io
import logging
from typing import Dict, Any, List

import fitz as pymupdf
from fitz import Document

from schemas.validation import ContentInfo, DocumentType

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Analyze document content for validation and processing hints"""

    def analyze(
        self,
        file_data: bytes,
        document_type: DocumentType,
        page_count: int = 0
    ) -> ContentInfo:
        """
        Analyze document content

        Args:
            file_data: File content as bytes
            document_type: Type of document
            page_count: Number of pages (if known)

        Returns:
            ContentInfo object with analysis results
        """
        content_info = ContentInfo()

        # Type-specific analysis
        if document_type == DocumentType.PDF:
            content_info = self._analyze_pdf(file_data)
        elif document_type == DocumentType.TXT:
            content_info = self._analyze_text(file_data)
        elif document_type in [DocumentType.HTML, DocumentType.MARKDOWN]:
            content_info = self._analyze_markup(file_data, document_type)
        else:
            # Basic analysis for unknown types
            content_info = self._analyze_generic(file_data)

        # Update page count if provided
        if page_count > 0:
            content_info.page_count = page_count

        # Calculate page density
        if content_info.page_count > 0 and content_info.word_count > 0:
            content_info.page_density = content_info.word_count / content_info.page_count

        return content_info

    def _analyze_pdf(self, file_data: bytes) -> ContentInfo:
        """
        Analyze PDF content

        Args:
            file_data: PDF file bytes

        Returns:
            ContentInfo with PDF analysis
        """
        content_info = ContentInfo()

        try:
            pdf_stream = io.BytesIO(file_data)
            doc: Document = pymupdf.open(stream=pdf_stream, filetype="pdf")

            content_info.page_count = len(doc)

            total_words = 0
            total_chars = 0
            total_lines = 0
            empty_pages = 0
            pages_with_images = 0
            pages_with_tables = 0
            total_images = 0
            total_tables = 0
            total_links = 0

            # Analyze each page
            for page_num in range(len(doc)):
                page = doc[page_num]

                # Extract and analyze text
                page_text = page.get_text("text")
                if not page_text.strip():
                    empty_pages += 1
                    # Check if page might need OCR
                    if page.get_images():
                        content_info.requires_ocr = True
                else:
                    # Count text metrics
                    words = page_text.split()
                    total_words += len(words)
                    total_chars += len(page_text)
                    total_lines += page_text.count('\n')

                # Check for images
                images = page.get_images()
                if images:
                    pages_with_images += 1
                    total_images += len(images)
                    content_info.has_images = True

                # Check for tables (basic detection)
                try:
                    tables = page.find_tables()
                    if tables:
                        pages_with_tables += 1
                        total_tables += len(tables)
                        content_info.has_tables = True
                except:
                    # Table detection might not be available
                    pass

                # Check for links
                links = page.get_links()
                if links:
                    total_links += len(links)
                    content_info.has_links = True

                # Check for forms
                widgets = page.widgets()
                if widgets:
                    content_info.has_forms = True
                    content_info.form_count += len(list(widgets))

            # Update content info
            content_info.word_count = total_words
            content_info.char_count = total_chars
            content_info.line_count = total_lines
            content_info.empty_page_count = empty_pages
            content_info.image_count = total_images
            content_info.table_count = total_tables
            content_info.link_count = total_links

            # Check for encryption
            content_info.has_encryption = doc.is_encrypted

            # Detect languages from sample text
            if total_words > 0:
                sample_text = ""
                for page_num in range(min(3, len(doc))):
                    sample_text += doc[page_num].get_text()[:500]
                content_info.detected_languages = self._detect_languages(sample_text)

            doc.close()

            logger.info(f"PDF analysis: {content_info.page_count} pages, {total_words} words, "
                       f"{total_images} images, {total_tables} tables")

        except Exception as e:
            logger.error(f"Error analyzing PDF content: {e}")

        return content_info

    def _analyze_text(self, file_data: bytes) -> ContentInfo:
        """
        Analyze text file content

        Args:
            file_data: Text file bytes

        Returns:
            ContentInfo with text analysis
        """
        content_info = ContentInfo()

        try:
            # Try to decode text
            text_content = None
            for encoding in ['utf-8', 'latin-1', 'windows-1254', 'iso-8859-9']:
                try:
                    text_content = file_data.decode(encoding)
                    content_info.encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue

            if text_content:
                # Count metrics
                lines = text_content.split('\n')
                words = text_content.split()

                content_info.line_count = len(lines)
                content_info.word_count = len(words)
                content_info.char_count = len(text_content)
                content_info.paragraph_count = text_content.count('\n\n') + 1

                # Approximate pages (50 lines per page)
                content_info.page_count = max(1, len(lines) // 50)

                # Detect languages
                sample = text_content[:2000]
                content_info.detected_languages = self._detect_languages(sample)

                # Check for markdown tables
                if '|' in text_content and '-|-' in text_content:
                    content_info.has_tables = True
                    content_info.table_count = text_content.count('\n|')

                # Check for links
                if 'http://' in text_content or 'https://' in text_content:
                    content_info.has_links = True
                    content_info.link_count = text_content.count('http://') + text_content.count('https://')

        except Exception as e:
            logger.error(f"Error analyzing text content: {e}")

        return content_info

    def _analyze_markup(self, file_data: bytes, document_type: DocumentType) -> ContentInfo:
        """
        Analyze markup content (HTML, Markdown)

        Args:
            file_data: File bytes
            document_type: Type of markup document

        Returns:
            ContentInfo with markup analysis
        """
        content_info = ContentInfo()

        try:
            # Decode content
            text_content = file_data.decode('utf-8', errors='ignore')

            # Basic text metrics
            content_info.char_count = len(text_content)
            content_info.line_count = text_content.count('\n')

            # Remove markup for word count
            import re
            if document_type == DocumentType.HTML:
                # Remove HTML tags
                clean_text = re.sub(r'<[^>]+>', '', text_content)
                # Check for specific elements
                content_info.has_tables = '<table' in text_content.lower()
                content_info.has_images = '<img' in text_content.lower()
                content_info.has_links = '<a ' in text_content.lower()

                if content_info.has_tables:
                    content_info.table_count = text_content.lower().count('<table')
                if content_info.has_images:
                    content_info.image_count = text_content.lower().count('<img')
                if content_info.has_links:
                    content_info.link_count = text_content.lower().count('<a ')

            else:  # Markdown
                # Basic markdown processing
                clean_text = re.sub(r'[#*`\[\]()]', '', text_content)
                # Check for markdown elements
                content_info.has_tables = '|' in text_content and '-|-' in text_content
                content_info.has_images = '![' in text_content
                content_info.has_links = '](' in text_content

                if content_info.has_tables:
                    content_info.table_count = len(re.findall(r'\n\|.*\|\n', text_content))
                if content_info.has_images:
                    content_info.image_count = text_content.count('![')
                if content_info.has_links:
                    content_info.link_count = text_content.count('](')

            # Word count from clean text
            words = clean_text.split()
            content_info.word_count = len(words)

            # Approximate pages
            content_info.page_count = max(1, content_info.word_count // 300)

            # Detect languages
            sample = clean_text[:2000]
            content_info.detected_languages = self._detect_languages(sample)

        except Exception as e:
            logger.error(f"Error analyzing markup content: {e}")

        return content_info

    def _analyze_generic(self, file_data: bytes) -> ContentInfo:
        """
        Generic content analysis for unknown document types

        Args:
            file_data: File bytes

        Returns:
            ContentInfo with basic analysis
        """
        content_info = ContentInfo()

        try:
            # Try to decode as text
            text_content = file_data.decode('utf-8', errors='ignore')

            # Basic metrics
            content_info.char_count = len(text_content)
            content_info.line_count = text_content.count('\n')
            content_info.word_count = len(text_content.split())
            content_info.page_count = max(1, content_info.word_count // 300)

        except:
            # Binary file - just set basic info
            content_info.char_count = len(file_data)

        return content_info

    def _detect_languages(self, text_sample: str) -> List[str]:
        """
        Detect languages in text sample

        Args:
            text_sample: Sample text

        Returns:
            List of detected language codes
        """
        languages = []

        if not text_sample:
            return languages

        # Turkish detection
        turkish_chars = 'çğıöşüÇĞİÖŞÜ'
        turkish_words = ['ve', 'ile', 'için', 'bir', 'bu', 'olan', 'olarak']

        turkish_char_count = sum(1 for char in text_sample if char in turkish_chars)
        turkish_word_count = sum(1 for word in turkish_words if f' {word} ' in text_sample.lower())

        if turkish_char_count > 5 or turkish_word_count > 3:
            languages.append('tr')

        # English detection
        english_words = ['the', 'and', 'for', 'with', 'this', 'that', 'from']
        english_word_count = sum(1 for word in english_words if f' {word} ' in text_sample.lower())

        if english_word_count > 3:
            languages.append('en')

        # If no language detected, mark as unknown
        if not languages:
            languages.append('unknown')

        return languages

    def get_processing_recommendations(self, content_info: ContentInfo) -> Dict[str, Any]:
        """
        Get processing recommendations based on content analysis

        Args:
            content_info: Content analysis results

        Returns:
            Dictionary with processing recommendations
        """
        recommendations = {}

        # Chunk size recommendation
        if content_info.has_tables:
            recommendations['chunk_size'] = 700  # Larger chunks for tables
        elif content_info.page_density > 500:
            recommendations['chunk_size'] = 600  # Dense content
        else:
            recommendations['chunk_size'] = 500  # Default

        # OCR recommendation
        recommendations['use_ocr'] = content_info.requires_ocr

        # Table extraction
        recommendations['extract_tables'] = content_info.has_tables

        # Image extraction
        recommendations['extract_images'] = content_info.has_images and content_info.image_count > 5

        # Parallel processing for large documents
        recommendations['parallel_processing'] = content_info.page_count > 50

        # Memory estimate
        recommendations['memory_estimate_mb'] = max(
            50,
            (content_info.char_count // 10000) * 5  # Rough estimate
        )

        return recommendations