"""
Retrieval and search schemas
"""

# Search schemas
from schemas.retrieval.search import (
    SearchType,
    SearchStrategy,
    SearchQuery,
    SearchFilter,
    SearchResult,
    SearchResponse,
    BulkSearchRequest,
    SearchAggregation,
    SearchContext,
    SearchMetrics,
    SearchExplanation
)

# Reranker schemas
from schemas.retrieval.reranker import (
    RerankerType,
    RerankerModel,
    RerankerConfig,
    RerankerRequest,
    RerankedResult,
    RerankerResponse,
    BatchRerankerRequest,
    RerankerComparison,
    RerankerMetrics,
    RerankingStrategy
)

# Hybrid search schemas
from schemas.retrieval.hybrid import (
    HybridSearchMethod,
    FusionMethod,
    HybridSearchConfig,
    HybridSearchQuery,
    HybridSearchResult,
    HybridSearchResponse,
    MultiStageSearch,
    HybridSearchOptimization,
    HybridSearchMetrics,
    HybridSearchExperiment
)

__all__ = [
    # Search
    "SearchType",
    "SearchStrategy",
    "SearchQuery",
    "SearchFilter",
    "SearchResult",
    "SearchResponse",
    "BulkSearchRequest",
    "SearchAggregation",
    "SearchContext",
    "SearchMetrics",
    "SearchExplanation",
    # Reranker
    "RerankerType",
    "RerankerModel",
    "RerankerConfig",
    "RerankerRequest",
    "RerankedResult",
    "RerankerResponse",
    "BatchRerankerRequest",
    "RerankerComparison",
    "RerankerMetrics",
    "RerankingStrategy",
    # Hybrid
    "HybridSearchMethod",
    "FusionMethod",
    "HybridSearchConfig",
    "HybridSearchQuery",
    "HybridSearchResult",
    "HybridSearchResponse",
    "MultiStageSearch",
    "HybridSearchOptimization",
    "HybridSearchMetrics",
    "HybridSearchExperiment",
]


# Helper functions
def create_search_query(
    query: str,
    search_type: str = "vector",
    top_k: int = 10,
    filters: dict = None
) -> SearchQuery:
    """
    Create a search query with defaults

    Args:
        query: Search query text
        search_type: Type of search (vector, keyword, hybrid)
        top_k: Number of results
        filters: Optional filters

    Returns:
        SearchQuery configured for the search
    """
    from schemas.retrieval.search import SearchQuery, SearchType

    return SearchQuery(
        query=query,
        search_type=SearchType(search_type),
        top_k=top_k,
        filters=filters or {}
    )


def create_reranker_config(
    reranker_type: str = "cross_encoder",
    model: str = None,
    top_n: int = None
) -> RerankerConfig:
    """
    Create reranker configuration

    Args:
        reranker_type: Type of reranker
        model: Model name or path
        top_n: Number of results to return

    Returns:
        RerankerConfig
    """
    from schemas.retrieval.reranker import RerankerConfig, RerankerType, RerankerModel

    if not model:
        if reranker_type == "cross_encoder":
            model = RerankerModel.MS_MARCO_MINILM
        elif reranker_type == "cohere":
            model = RerankerModel.COHERE_RERANK_ENGLISH

    return RerankerConfig(
        type=RerankerType(reranker_type),
        model=model,
        top_n=top_n
    )


def create_hybrid_config(
    method: str = "vector_keyword",
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> HybridSearchConfig:
    """
    Create hybrid search configuration

    Args:
        method: Hybrid search method
        vector_weight: Weight for vector search
        keyword_weight: Weight for keyword search

    Returns:
        HybridSearchConfig
    """
    from schemas.retrieval.hybrid import HybridSearchConfig, HybridSearchMethod, FusionMethod

    return HybridSearchConfig(
        method=HybridSearchMethod(method),
        fusion_method=FusionMethod.RRF,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight
    )


def calculate_rrf_score(
    ranks: list,
    k: int = 60
) -> float:
    """
    Calculate Reciprocal Rank Fusion score

    Args:
        ranks: List of ranks from different searches
        k: RRF parameter (default 60)

    Returns:
        RRF score
    """
    score = 0.0
    for rank in ranks:
        score += 1.0 / (k + rank)
    return score


def merge_search_results(
    results_list: list,
    fusion_method: str = "rrf",
    weights: list = None
) -> list:
    """
    Merge results from multiple searches

    Args:
        results_list: List of result lists
        fusion_method: Method to use (rrf, linear, weighted)
        weights: Weights for weighted fusion

    Returns:
        Merged and ranked results
    """
    if fusion_method == "rrf":
        # Create a mapping of result_id to ranks
        result_ranks = {}
        for results in results_list:
            for i, result in enumerate(results):
                if result.id not in result_ranks:
                    result_ranks[result.id] = []
                result_ranks[result.id].append(i + 1)  # 1-indexed rank

        # Calculate RRF scores
        rrf_scores = {}
        for result_id, ranks in result_ranks.items():
            rrf_scores[result_id] = calculate_rrf_score(ranks)

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Return merged results
        merged = []
        seen = set()
        for results in results_list:
            for result in results:
                if result.id in sorted_ids and result.id not in seen:
                    result.score = rrf_scores[result.id]
                    merged.append(result)
                    seen.add(result.id)

        return merged

    elif fusion_method == "weighted" and weights:
        # Weighted combination
        result_scores = {}
        result_objects = {}

        for weight, results in zip(weights, results_list):
            for result in results:
                if result.id not in result_scores:
                    result_scores[result.id] = 0.0
                    result_objects[result.id] = result
                result_scores[result.id] += weight * result.score

        # Sort by weighted score
        sorted_ids = sorted(result_scores.keys(), key=lambda x: result_scores[x], reverse=True)

        merged = []
        for result_id in sorted_ids:
            result = result_objects[result_id]
            result.score = result_scores[result_id]
            merged.append(result)

        return merged

    else:
        # Simple concatenation
        merged = []
        seen = set()
        for results in results_list:
            for result in results:
                if result.id not in seen:
                    merged.append(result)
                    seen.add(result.id)
        return merged


def evaluate_search_results(
    results: list,
    relevant_ids: set,
    k: int = 10
) -> dict:
    """
    Evaluate search results quality

    Args:
        results: Search results
        relevant_ids: Set of relevant document IDs
        k: Cutoff for evaluation

    Returns:
        Dictionary with evaluation metrics
    """
    results_at_k = results[:k]
    retrieved_ids = {r.id for r in results_at_k}

    # Calculate metrics
    relevant_retrieved = retrieved_ids.intersection(relevant_ids)

    precision = len(relevant_retrieved) / k if k > 0 else 0
    recall = len(relevant_retrieved) / len(relevant_ids) if relevant_ids else 0

    # Calculate Average Precision
    ap = 0.0
    relevant_found = 0
    for i, result in enumerate(results_at_k):
        if result.id in relevant_ids:
            relevant_found += 1
            ap += relevant_found / (i + 1)

    ap = ap / min(len(relevant_ids), k) if relevant_ids else 0

    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "f1_score": 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0,
        "average_precision": ap,
        "relevant_found": len(relevant_retrieved),
        "total_relevant": len(relevant_ids)
    }