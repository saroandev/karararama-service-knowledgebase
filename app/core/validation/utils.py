"""
Utility functions for document validation
"""
import hashlib
import mimetypes
from typing import Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def generate_document_hash(file_data: bytes) -> Tuple[str, str, str]:
    """
    Generate hash values for document

    Args:
        file_data: File content as bytes

    Returns:
        Tuple of (document_id, md5_hash, sha256_hash)
    """
    # Generate MD5 hash
    md5_hash = hashlib.md5(file_data).hexdigest()

    # Generate SHA256 hash
    sha256_hash = hashlib.sha256(file_data).hexdigest()

    # Create document ID from MD5 hash (compatible with existing system)
    document_id = f"doc_{md5_hash[:16]}"

    return document_id, md5_hash, sha256_hash


def detect_mime_type(filename: str) -> Optional[str]:
    """
    Detect MIME type from filename

    Args:
        filename: Name of the file

    Returns:
        MIME type string or None
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def get_file_extension(filename: str) -> str:
    """
    Extract file extension from filename

    Args:
        filename: Name of the file

    Returns:
        File extension without dot, lowercase
    """
    if not filename or '.' not in filename:
        return ""
    return filename.rsplit('.', 1)[-1].lower()


def check_magic_bytes(file_data: bytes) -> Dict[str, bool]:
    """
    Check magic bytes to determine file type

    Args:
        file_data: File content as bytes

    Returns:
        Dictionary with file type checks
    """
    if not file_data or len(file_data) < 8:
        return {
            "is_pdf": False,
            "is_docx": False,
            "is_txt": False,
            "is_html": False
        }

    # Check for PDF
    is_pdf = file_data[:4] == b'%PDF'

    # Check for DOCX (ZIP archive starting with PK)
    is_docx = (
        file_data[:2] == b'PK' and
        len(file_data) > 4 and
        file_data[2:4] in [b'\x03\x04', b'\x05\x06', b'\x07\x08']
    )

    # Check for HTML
    is_html = False
    try:
        start = file_data[:1024].decode('utf-8', errors='ignore').lower()
        is_html = '<!doctype html' in start or '<html' in start
    except:
        pass

    # Check for text file (can decode as UTF-8)
    is_txt = False
    try:
        file_data[:1024].decode('utf-8')
        is_txt = not is_pdf and not is_docx and not is_html
    except:
        pass

    return {
        "is_pdf": is_pdf,
        "is_docx": is_docx,
        "is_txt": is_txt,
        "is_html": is_html
    }


def estimate_processing_requirements(
    file_size: int,
    page_count: int = 0,
    has_images: bool = False,
    has_tables: bool = False
) -> Dict[str, Any]:
    """
    Estimate processing requirements for document

    Args:
        file_size: File size in bytes
        page_count: Number of pages
        has_images: Whether document contains images
        has_tables: Whether document contains tables

    Returns:
        Dictionary with processing hints
    """
    # Base chunk size recommendation
    if file_size < 1024 * 1024:  # < 1MB
        chunk_size = 300
    elif file_size < 10 * 1024 * 1024:  # < 10MB
        chunk_size = 500
    else:
        chunk_size = 700

    # Adjust for content complexity
    if has_tables:
        chunk_size = int(chunk_size * 1.2)  # Larger chunks for tables
    if has_images:
        chunk_size = int(chunk_size * 0.8)  # Smaller chunks when images present

    # Estimate chunk count
    avg_chars_per_page = 2000  # Approximate
    if page_count > 0:
        estimated_chars = page_count * avg_chars_per_page
        estimated_chunks = estimated_chars // (chunk_size * 4)  # Rough token to char ratio
    else:
        # Fallback estimation from file size
        estimated_chunks = max(1, file_size // (chunk_size * 100))

    # Processing strategy
    use_ocr = False  # Will be determined by content analyzer
    extract_tables = has_tables
    extract_images = has_images

    return {
        "recommended_chunk_size": chunk_size,
        "estimated_chunks": estimated_chunks,
        "use_ocr": use_ocr,
        "extract_tables": extract_tables,
        "extract_images": extract_images,
        "parallel_processing": page_count > 50,
        "memory_estimate_mb": max(50, file_size // (1024 * 10))  # Rough estimate
    }


def validate_encoding(file_data: bytes) -> Tuple[bool, str, Optional[str]]:
    """
    Validate and detect file encoding

    Args:
        file_data: File content as bytes

    Returns:
        Tuple of (is_valid, detected_encoding, error_message)
    """
    # For PDF files, encoding check is not applicable
    if file_data[:4] == b'%PDF':
        return True, "binary", None

    # Try common encodings
    encodings = ['utf-8', 'utf-16', 'latin-1', 'windows-1254', 'iso-8859-9']  # Turkish encodings included

    for encoding in encodings:
        try:
            file_data[:1024].decode(encoding)
            return True, encoding, None
        except (UnicodeDecodeError, LookupError):
            continue

    return False, "unknown", "Could not detect valid text encoding"


def calculate_file_metrics(file_data: bytes) -> Dict[str, Any]:
    """
    Calculate basic file metrics

    Args:
        file_data: File content as bytes

    Returns:
        Dictionary with file metrics
    """
    file_size = len(file_data)
    file_size_mb = file_size / (1024 * 1024)

    # Calculate compression ratio estimate (for text files)
    unique_bytes = len(set(file_data[:10240])) if len(file_data) > 10240 else len(set(file_data))
    compression_estimate = unique_bytes / min(256, len(file_data[:10240]))

    return {
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size_mb, 2),
        "is_empty": file_size == 0,
        "is_large": file_size_mb > 50,
        "compression_estimate": round(compression_estimate, 2),
        "likely_compressed": compression_estimate > 0.7
    }