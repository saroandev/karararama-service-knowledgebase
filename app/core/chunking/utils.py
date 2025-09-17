"""
Utility functions for chunking operations
"""
import hashlib
import re
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


def token_count(text: str) -> int:
    """
    Estimate token count for text
    Simple approximation: ~4 characters per token

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count
    """
    return len(text) // 4


def clean_text(text: str) -> str:
    """
    Clean and normalize text for chunking

    Args:
        text: Raw text

    Returns:
        Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove control characters
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)

    # Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove excessive line breaks (more than 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def calculate_page_boundaries(pages: List[Any]) -> List[Tuple[int, int, int]]:
    """
    Calculate character boundaries for each page

    Args:
        pages: List of page objects with text

    Returns:
        List of tuples (start_pos, end_pos, page_number)
    """
    boundaries = []
    current_pos = 0

    for page in pages:
        page_text = page.text if hasattr(page, 'text') else str(page)
        page_length = len(page_text)
        page_number = page.page_number if hasattr(page, 'page_number') else len(boundaries) + 1

        boundaries.append((
            current_pos,
            current_pos + page_length,
            page_number
        ))

        # Account for page separator
        current_pos += page_length + 2  # "\n\n"

    return boundaries


def get_pages_for_position(position: int, boundaries: List[Tuple[int, int, int]]) -> List[int]:
    """
    Determine which pages a text position spans

    Args:
        position: Character position in combined text
        boundaries: Page boundaries from calculate_page_boundaries

    Returns:
        List of page numbers
    """
    pages = []

    for start_pos, end_pos, page_num in boundaries:
        if start_pos <= position < end_pos:
            pages.append(page_num)

    return pages if pages else [1]  # Default to page 1 if not found


def generate_chunk_hash(text: str) -> str:
    """
    Generate hash for chunk text (for deduplication)

    Args:
        text: Chunk text

    Returns:
        MD5 hash of text
    """
    return hashlib.md5(text.encode()).hexdigest()[:16]


def merge_chunks(chunks: List[Any], max_size: int = 1000) -> List[Any]:
    """
    Merge small chunks to avoid fragmentation

    Args:
        chunks: List of chunks to merge
        max_size: Maximum size after merging

    Returns:
        List of merged chunks
    """
    if not chunks:
        return []

    merged = []
    current_chunk = None

    for chunk in chunks:
        chunk_size = chunk.token_count if hasattr(chunk, 'token_count') else len(chunk.text) // 4

        if current_chunk is None:
            current_chunk = chunk
        elif (current_chunk.token_count + chunk_size) <= max_size:
            # Merge chunks
            current_chunk.text += "\n" + chunk.text
            current_chunk.token_count += chunk_size
            current_chunk.char_count += chunk.char_count if hasattr(chunk, 'char_count') else len(chunk.text)

            # Merge metadata
            if hasattr(chunk, 'metadata'):
                for key, value in chunk.metadata.items():
                    if key not in current_chunk.metadata:
                        current_chunk.metadata[key] = value
        else:
            # Start new chunk
            merged.append(current_chunk)
            current_chunk = chunk

    if current_chunk:
        merged.append(current_chunk)

    return merged


def split_by_separator(
    text: str,
    separators: List[str] = None
) -> List[str]:
    """
    Split text by hierarchical separators

    Args:
        text: Text to split
        separators: List of separators in order of preference

    Returns:
        List of text segments
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    segments = [text]

    for separator in separators:
        if not separator:
            continue

        new_segments = []
        for segment in segments:
            if separator in segment:
                parts = segment.split(separator)
                # Keep separator with the part
                for i, part in enumerate(parts[:-1]):
                    new_segments.append(part + separator)
                new_segments.append(parts[-1])
            else:
                new_segments.append(segment)

        segments = new_segments

    return [s for s in segments if s.strip()]