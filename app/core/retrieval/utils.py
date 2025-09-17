"""
Utility functions for retrieval operations
"""
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


def build_filter_expression(filters: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Build Milvus filter expression from filters dictionary

    Args:
        filters: Dictionary of filters

    Returns:
        Filter expression string or None

    Examples:
        >>> build_filter_expression({"document_id": "doc1"})
        'document_id == "doc1"'
        >>> build_filter_expression({"page_number": [1, 2, 3]})
        '(page_number == 1 or page_number == 2 or page_number == 3)'
    """
    if not filters:
        return None

    expressions = []

    # Document ID filter
    if "document_id" in filters:
        doc_id = filters["document_id"]
        if isinstance(doc_id, list):
            doc_expr = " or ".join([f'document_id == "{d}"' for d in doc_id])
            expressions.append(f"({doc_expr})")
        else:
            expressions.append(f'document_id == "{doc_id}"')

    # Page number filter
    if "page_number" in filters:
        page = filters["page_number"]
        if isinstance(page, list):
            page_expr = " or ".join([f"page_number == {p}" for p in page])
            expressions.append(f"({page_expr})")
        else:
            expressions.append(f"page_number == {page}")

    # Chunk index filter
    if "chunk_index" in filters:
        chunk_idx = filters["chunk_index"]
        if isinstance(chunk_idx, list):
            chunk_expr = " or ".join([f"chunk_index == {c}" for c in chunk_idx])
            expressions.append(f"({chunk_expr})")
        else:
            expressions.append(f"chunk_index == {chunk_idx}")

    # Date range filter (if metadata contains dates)
    if "date_from" in filters or "date_to" in filters:
        if "date_from" in filters:
            expressions.append(f"created_at >= {filters['date_from']}")
        if "date_to" in filters:
            expressions.append(f"created_at <= {filters['date_to']}")

    # Combine expressions
    if expressions:
        return " and ".join(expressions)

    return None


def calculate_text_similarity(text1: str, text2: str, method: str = "jaccard") -> float:
    """
    Calculate text similarity between two strings

    Args:
        text1: First text
        text2: Second text
        method: Similarity method ('jaccard', 'overlap', 'dice')

    Returns:
        Similarity score [0, 1]
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    if method == "jaccard":
        return len(intersection) / len(union)
    elif method == "overlap":
        return len(intersection) / min(len(words1), len(words2))
    elif method == "dice":
        return 2 * len(intersection) / (len(words1) + len(words2))
    else:
        return len(intersection) / len(union)  # Default to Jaccard


def enrich_results_from_storage(
    results: List[Dict[str, Any]],
    storage_client: Any,
    batch_size: int = 50
) -> List[Dict[str, Any]]:
    """
    Enrich search results with full text from storage

    Args:
        results: Search results to enrich
        storage_client: Storage client for fetching data
        batch_size: Batch size for fetching

    Returns:
        Enriched results
    """
    if not results:
        return []

    # Process in batches
    enriched_results = []
    for i in range(0, len(results), batch_size):
        batch = results[i:i + batch_size]

        # Collect MinIO paths
        minio_paths = []
        for result in batch:
            path = result.get("minio_object_path")
            minio_paths.append(path if path else None)

        # Batch fetch from storage
        valid_paths = [p for p in minio_paths if p]
        if valid_paths:
            try:
                chunk_data_list = storage_client.get_chunks_batch(valid_paths)
            except Exception as e:
                logger.error(f"Error fetching chunks from storage: {e}")
                chunk_data_list = []
        else:
            chunk_data_list = []

        # Map back to results
        chunk_idx = 0
        for j, result in enumerate(batch):
            if minio_paths[j]:
                if chunk_idx < len(chunk_data_list) and chunk_data_list[chunk_idx]:
                    # Merge storage data with search result
                    chunk_data = chunk_data_list[chunk_idx]
                    result["text"] = chunk_data.get("text", result.get("text", ""))
                    result["token_count"] = chunk_data.get("token_count", 0)
                    result["char_count"] = chunk_data.get("char_count", 0)
                    # Merge metadata
                    if "metadata" in chunk_data:
                        if "metadata" not in result:
                            result["metadata"] = {}
                        result["metadata"].update(chunk_data["metadata"])
                chunk_idx += 1

            enriched_results.append(result)

    return enriched_results


def apply_mmr_selection(
    results: List[Dict[str, Any]],
    top_k: int,
    diversity_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Apply Maximal Marginal Relevance selection for diversity

    Args:
        results: Candidate results
        top_k: Number of results to select
        diversity_threshold: Weight for diversity (0=only relevance, 1=only diversity)

    Returns:
        Selected diverse results
    """
    if not results or top_k <= 0:
        return []

    if len(results) <= top_k:
        return results

    # Start with the best match
    selected = [results[0]]
    candidates = results[1:]

    while len(selected) < top_k and candidates:
        mmr_scores = []

        for candidate in candidates:
            # Relevance score (already computed)
            relevance = candidate.get("score", 0)

            # Max similarity to already selected items
            max_sim = 0
            for selected_item in selected:
                sim = calculate_text_similarity(
                    candidate.get("text", ""),
                    selected_item.get("text", "")
                )
                max_sim = max(max_sim, sim)

            # MMR score
            mmr = diversity_threshold * relevance - (1 - diversity_threshold) * max_sim
            mmr_scores.append(mmr)

        # Select best MMR candidate
        best_idx = np.argmax(mmr_scores)
        selected.append(candidates[best_idx])
        candidates.pop(best_idx)

    return selected


def deduplicate_results(
    results: List[Dict[str, Any]],
    key_field: str = "chunk_id",
    score_field: str = "score"
) -> List[Dict[str, Any]]:
    """
    Remove duplicate results, keeping the one with highest score

    Args:
        results: Results to deduplicate
        key_field: Field to use as unique identifier
        score_field: Field to use for selecting best duplicate

    Returns:
        Deduplicated results
    """
    seen = {}
    for result in results:
        key = result.get(key_field, result.get("id"))
        if key:
            if key not in seen:
                seen[key] = result
            else:
                # Keep the one with higher score
                if result.get(score_field, 0) > seen[key].get(score_field, 0):
                    seen[key] = result

    # Return in original order
    deduplicated = []
    for result in results:
        key = result.get(key_field, result.get("id"))
        if key and key in seen and seen[key] is result:
            deduplicated.append(result)

    return deduplicated


def merge_search_results(
    *result_lists: List[Dict[str, Any]],
    method: str = "union",
    key_field: str = "chunk_id"
) -> List[Dict[str, Any]]:
    """
    Merge multiple search result lists

    Args:
        *result_lists: Variable number of result lists
        method: Merge method ('union', 'intersection')
        key_field: Field to use as unique identifier

    Returns:
        Merged results
    """
    if not result_lists:
        return []

    if method == "intersection":
        # Keep only results that appear in all lists
        keys_sets = []
        for results in result_lists:
            keys = set()
            for result in results:
                key = result.get(key_field, result.get("id"))
                if key:
                    keys.add(key)
            keys_sets.append(keys)

        # Find intersection
        common_keys = set.intersection(*keys_sets) if keys_sets else set()

        # Collect results with common keys
        merged = []
        for results in result_lists:
            for result in results:
                key = result.get(key_field, result.get("id"))
                if key and key in common_keys:
                    merged.append(result)
                    common_keys.remove(key)  # Only add once

    else:  # union
        # Keep all unique results
        seen_keys = set()
        merged = []
        for results in result_lists:
            for result in results:
                key = result.get(key_field, result.get("id"))
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    merged.append(result)

    return merged


def reciprocal_rank_fusion(
    result_lists: List[List[Dict[str, Any]]],
    k: int = 60,
    key_field: str = "chunk_id"
) -> List[Dict[str, Any]]:
    """
    Fuse multiple result lists using Reciprocal Rank Fusion

    Args:
        result_lists: List of result lists
        k: RRF parameter (typically 60)
        key_field: Field to use as unique identifier

    Returns:
        Fused results sorted by RRF score
    """
    rrf_scores = defaultdict(lambda: {"score": 0, "result": None})

    for results in result_lists:
        for rank, result in enumerate(results):
            key = result.get(key_field, result.get("id"))
            if key:
                # Add reciprocal rank score
                rrf_scores[key]["score"] += 1 / (k + rank + 1)
                # Keep the result object (prefer first occurrence)
                if rrf_scores[key]["result"] is None:
                    rrf_scores[key]["result"] = result

    # Sort by RRF score
    sorted_items = sorted(
        rrf_scores.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    # Extract results and add RRF scores
    fused_results = []
    for item in sorted_items:
        if item["result"]:
            result = item["result"].copy()
            result["rrf_score"] = item["score"]
            fused_results.append(result)

    return fused_results


def filter_by_score_threshold(
    results: List[Dict[str, Any]],
    threshold: float,
    score_field: str = "score"
) -> List[Dict[str, Any]]:
    """
    Filter results by minimum score threshold

    Args:
        results: Results to filter
        threshold: Minimum score threshold
        score_field: Field containing the score

    Returns:
        Filtered results
    """
    return [
        result for result in results
        if result.get(score_field, 0) >= threshold
    ]


def group_results_by_document(
    results: List[Dict[str, Any]],
    doc_field: str = "document_id"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group search results by document

    Args:
        results: Results to group
        doc_field: Field containing document ID

    Returns:
        Dictionary mapping document ID to list of results
    """
    grouped = defaultdict(list)
    for result in results:
        doc_id = result.get(doc_field)
        if doc_id:
            grouped[doc_id].append(result)
    return dict(grouped)