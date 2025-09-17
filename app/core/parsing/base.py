"""
Base classes for document parsing
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

# Import schemas from centralized location
from schemas.parsing import PageContent, DocumentMetadata


class AbstractParser(ABC):
    """Abstract base class for all document parser implementations"""

    def __init__(self):
        """Initialize the parser"""
        self.supported_formats = []

    @abstractmethod
    def extract_text(
        self,
        file_data: bytes,
        file_type: Optional[str] = None
    ) -> Tuple[List[PageContent], DocumentMetadata]:
        """
        Extract text and metadata from document

        Args:
            file_data: Document file bytes
            file_type: File type hint (e.g., 'pdf', 'docx')

        Returns:
            Tuple of (list of PageContent, DocumentMetadata)
        """
        pass

    @abstractmethod
    def extract_text_with_layout(
        self,
        file_data: bytes,
        file_type: Optional[str] = None
    ) -> List[PageContent]:
        """
        Extract text while preserving layout information

        Args:
            file_data: Document file bytes
            file_type: File type hint

        Returns:
            List of PageContent with layout preserved
        """
        pass

    def is_supported(self, file_type: str) -> bool:
        """
        Check if file type is supported

        Args:
            file_type: File extension or type

        Returns:
            True if supported, False otherwise
        """
        return file_type.lower() in [fmt.lower() for fmt in self.supported_formats]

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            # Remove leading/trailing whitespace
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Replace multiple spaces with single space
            line = ' '.join(line.split())

            cleaned_lines.append(line)

        # Join with single newline
        cleaned_text = '\n'.join(cleaned_lines)

        # Remove control characters (except newlines and tabs)
        cleaned_text = ''.join(
            char for char in cleaned_text
            if char == '\n' or char == '\t' or (ord(char) >= 32 and ord(char) <= 126) or ord(char) > 127
        )

        return cleaned_text