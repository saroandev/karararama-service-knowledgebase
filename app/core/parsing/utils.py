"""
Utility functions for document parsing
"""
import logging
from typing import Optional, Dict, Any
import mimetypes

# Optional import - python-magic may not be installed
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

logger = logging.getLogger(__name__)


def detect_file_type(file_data: bytes, filename: Optional[str] = None) -> str:
    """
    Detect file type from bytes or filename

    Args:
        file_data: File content as bytes
        filename: Optional filename with extension

    Returns:
        File type string (e.g., 'pdf', 'docx')
    """
    file_type = None

    # Try to detect from file content using python-magic if available
    if MAGIC_AVAILABLE:
        try:
            mime = magic.from_buffer(file_data, mime=True)
            if mime == 'application/pdf':
                file_type = 'pdf'
            elif mime == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                file_type = 'docx'
            elif mime == 'application/msword':
                file_type = 'doc'
            elif mime == 'text/plain':
                file_type = 'txt'
            elif mime == 'text/markdown':
                file_type = 'md'
        except Exception as e:
            logger.warning(f"Could not detect file type from content: {e}")

    # Fallback to filename extension if provided
    if not file_type and filename:
        ext = filename.lower().split('.')[-1] if '.' in filename else None
        if ext:
            file_type = ext

    return file_type or 'unknown'


def estimate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """
    Estimate reading time for text

    Args:
        text: Text content
        words_per_minute: Average reading speed

    Returns:
        Estimated reading time in minutes
    """
    word_count = len(text.split())
    reading_time = word_count / words_per_minute
    return max(1, round(reading_time))


def extract_text_statistics(text: str) -> Dict[str, Any]:
    """
    Extract statistics from text

    Args:
        text: Text content

    Returns:
        Dictionary with text statistics
    """
    lines = text.split('\n')
    words = text.split()
    sentences = text.split('.')

    return {
        'char_count': len(text),
        'word_count': len(words),
        'line_count': len(lines),
        'sentence_count': len(sentences),
        'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0,
        'avg_sentence_length': len(words) / len(sentences) if sentences else 0,
        'reading_time_minutes': estimate_reading_time(text)
    }


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to append if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    # Try to truncate at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')

    if last_space > max_length * 0.8:  # If space is reasonably close to end
        truncated = truncated[:last_space]

    return truncated + suffix


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text

    Args:
        text: Text with potentially irregular whitespace

    Returns:
        Text with normalized whitespace
    """
    # Replace multiple spaces with single space
    text = ' '.join(text.split())

    # Replace multiple newlines with double newline
    lines = text.split('\n')
    normalized_lines = []
    for line in lines:
        line = line.strip()
        if line:
            normalized_lines.append(line)

    return '\n'.join(normalized_lines)


def extract_keywords(text: str, max_keywords: int = 10) -> list:
    """
    Extract keywords from text (basic implementation)

    Args:
        text: Text to extract keywords from
        max_keywords: Maximum number of keywords

    Returns:
        List of keywords
    """
    # This is a basic implementation
    # For production, consider using NLTK or spaCy
    import re
    from collections import Counter

    # Convert to lowercase and extract words
    words = re.findall(r'\b[a-z]+\b', text.lower())

    # Filter out common stop words (basic list)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
        'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
        'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 'just', 'as'
    }

    # Filter words
    filtered_words = [w for w in words if w not in stop_words and len(w) > 3]

    # Count word frequency
    word_freq = Counter(filtered_words)

    # Return most common keywords
    return [word for word, _ in word_freq.most_common(max_keywords)]