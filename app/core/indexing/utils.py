"""
Utility functions for vector indexing
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_chunk_id(document_id: str, chunk_index: int) -> str:
    """
    Generate unique ID for a chunk

    Args:
        document_id: Document identifier
        chunk_index: Index of chunk within document

    Returns:
        Unique chunk ID
    """
    return f"{document_id}_chunk_{chunk_index:04d}"


def generate_document_id(content: bytes, prefix: str = "doc") -> str:
    """
    Generate unique document ID from content

    Args:
        content: Document content as bytes
        prefix: Prefix for the ID

    Returns:
        Unique document ID
    """
    doc_hash = hashlib.md5(content).hexdigest()
    return f"{prefix}_{doc_hash[:16]}"


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """
    Normalize embedding vector to unit length

    Args:
        embedding: Embedding vector

    Returns:
        Normalized embedding vector
    """
    norm = np.linalg.norm(embedding)
    if norm > 0:
        return embedding / norm
    return embedding


def batch_embeddings(
    embeddings: List[np.ndarray],
    batch_size: int = 100
) -> List[List[np.ndarray]]:
    """
    Split embeddings into batches

    Args:
        embeddings: List of embeddings
        batch_size: Size of each batch

    Returns:
        List of embedding batches
    """
    batches = []
    for i in range(0, len(embeddings), batch_size):
        batch = embeddings[i:i + batch_size]
        batches.append(batch)
    return batches


def calculate_similarity(
    embedding1: np.ndarray,
    embedding2: np.ndarray,
    metric: str = "cosine"
) -> float:
    """
    Calculate similarity between two embeddings

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        metric: Similarity metric ("cosine", "euclidean", "dot")

    Returns:
        Similarity score
    """
    if metric == "cosine":
        # Cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        if norm1 > 0 and norm2 > 0:
            return float(dot_product / (norm1 * norm2))
        return 0.0

    elif metric == "euclidean":
        # Euclidean distance (inverted for similarity)
        distance = np.linalg.norm(embedding1 - embedding2)
        return float(1.0 / (1.0 + distance))

    elif metric == "dot":
        # Dot product
        return float(np.dot(embedding1, embedding2))

    else:
        raise ValueError(f"Unknown metric: {metric}")


def filter_search_results(
    results: List[Dict[str, Any]],
    min_score: Optional[float] = None,
    max_results: Optional[int] = None,
    unique_documents: bool = False
) -> List[Dict[str, Any]]:
    """
    Filter search results based on criteria

    Args:
        results: List of search results
        min_score: Minimum similarity score
        max_results: Maximum number of results
        unique_documents: Whether to keep only one result per document

    Returns:
        Filtered list of results
    """
    filtered = results.copy()

    # Filter by minimum score
    if min_score is not None:
        filtered = [r for r in filtered if r.get("score", 0) >= min_score]

    # Keep only unique documents
    if unique_documents:
        seen_docs = set()
        unique_results = []
        for result in filtered:
            doc_id = result.get("document_id")
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                unique_results.append(result)
        filtered = unique_results

    # Limit results
    if max_results is not None:
        filtered = filtered[:max_results]

    return filtered


def merge_search_results(
    results_list: List[List[Dict[str, Any]]],
    strategy: str = "interleave"
) -> List[Dict[str, Any]]:
    """
    Merge multiple search result lists

    Args:
        results_list: List of search result lists
        strategy: Merge strategy ("interleave", "concatenate", "best_score")

    Returns:
        Merged list of results
    """
    if not results_list:
        return []

    if strategy == "interleave":
        # Interleave results from different lists
        merged = []
        max_len = max(len(results) for results in results_list)
        for i in range(max_len):
            for results in results_list:
                if i < len(results):
                    merged.append(results[i])
        return merged

    elif strategy == "concatenate":
        # Simply concatenate all lists
        merged = []
        for results in results_list:
            merged.extend(results)
        return merged

    elif strategy == "best_score":
        # Merge and sort by score
        merged = []
        for results in results_list:
            merged.extend(results)
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged

    else:
        raise ValueError(f"Unknown merge strategy: {strategy}")


def prepare_chunk_metadata(
    chunk: Dict[str, Any],
    document_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Prepare chunk metadata for indexing

    Args:
        chunk: Chunk dictionary
        document_metadata: Optional document-level metadata

    Returns:
        Prepared metadata dictionary
    """
    metadata = chunk.get("metadata", {}).copy()

    # Add document metadata if provided
    if document_metadata:
        metadata["document_title"] = document_metadata.get("title")
        metadata["document_author"] = document_metadata.get("author")
        metadata["document_date"] = document_metadata.get("creation_date")

    # Add indexing metadata
    metadata["indexed_at"] = datetime.now().isoformat()
    metadata["chunk_index"] = chunk.get("chunk_index", 0)
    metadata["page_number"] = chunk.get("page_number", metadata.get("page_number", 0))

    # Add text statistics
    text = chunk.get("text", "")
    metadata["char_count"] = len(text)
    metadata["word_count"] = len(text.split())

    return metadata


def validate_embeddings(
    embeddings: List[np.ndarray],
    expected_dimension: int
) -> Tuple[bool, List[str]]:
    """
    Validate embeddings for indexing

    Args:
        embeddings: List of embedding vectors
        expected_dimension: Expected dimension of embeddings

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not embeddings:
        errors.append("No embeddings provided")
        return False, errors

    for i, embedding in enumerate(embeddings):
        if not isinstance(embedding, np.ndarray):
            errors.append(f"Embedding {i} is not a numpy array")

        if embedding.shape[0] != expected_dimension:
            errors.append(f"Embedding {i} has wrong dimension: {embedding.shape[0]} != {expected_dimension}")

        if np.isnan(embedding).any():
            errors.append(f"Embedding {i} contains NaN values")

        if np.isinf(embedding).any():
            errors.append(f"Embedding {i} contains infinite values")

    return len(errors) == 0, errors