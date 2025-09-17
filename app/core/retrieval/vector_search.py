"""
Vector search retriever implementation
"""
import logging
from typing import List, Dict, Any, Optional
import numpy as np

from app.core.retrieval.base import AbstractRetriever
from app.core.indexing import default_indexer as indexer
from app.core.embeddings import default_embedding_generator as embedder
from app.storage import storage
from app.config import settings

logger = logging.getLogger(__name__)


class VectorSearchRetriever(AbstractRetriever):
    """
    Basic vector search retriever using embeddings and vector database
    """

    def __init__(self, use_reranker: bool = False):
        """
        Initialize the vector search retriever

        Args:
            use_reranker: Whether to use reranking
        """
        super().__init__(use_reranker)
        self.indexer = indexer
        self.embedder = embedder
        self.storage = storage

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_reranker: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks using vector similarity search

        Args:
            query: Query text
            top_k: Number of results to return
            filters: Optional filters for search
            use_reranker: Whether to use reranker (not used in base vector search)

        Returns:
            List of relevant chunks with scores
        """
        # Generate query embedding
        query_embedding = self.embedder.generate_embedding(query)

        # Convert filters to expression
        filter_expr = self._build_filter_expression(filters)

        # Search
        results = self.indexer.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expr
        )

        # Enrich results with full text from storage
        enriched_results = self._enrich_results(results)

        return enriched_results

    def retrieve_diverse(
        self,
        query: str,
        top_k: int = 10,
        diversity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve diverse results using MMR (Maximal Marginal Relevance)

        Args:
            query: Query text
            top_k: Number of results to return
            diversity_threshold: Similarity threshold for diversity

        Returns:
            Diverse search results
        """
        # Get initial candidates (3x more than needed)
        candidates = self.retrieve(query, top_k * 3)

        if not candidates:
            return []

        # Implement MMR
        selected = [candidates[0]]  # Start with best match
        candidates = candidates[1:]

        while len(selected) < top_k and candidates:
            # Calculate MMR scores
            mmr_scores = []

            for candidate in candidates:
                # Relevance to query (already have this)
                relevance = candidate["score"]

                # Max similarity to already selected
                max_sim = 0
                for selected_item in selected:
                    # Simple text similarity
                    sim = self._text_similarity(
                        candidate["text"],
                        selected_item["text"]
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

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword search

        Args:
            query: Query text
            top_k: Number of results
            keyword_weight: Weight for keyword search (0-1)

        Returns:
            Combined search results
        """
        # Semantic search
        semantic_results = self.retrieve(query, top_k * 2)

        # Simple keyword scoring
        query_words = set(query.lower().split())

        for result in semantic_results:
            text_words = set(result["text"].lower().split())
            keyword_score = len(query_words & text_words) / len(query_words) if query_words else 0

            # Combine scores
            result["hybrid_score"] = (
                (1 - keyword_weight) * result["score"] +
                keyword_weight * keyword_score
            )

        # Sort by hybrid score
        semantic_results.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return semantic_results[:top_k]

    def _build_filter_expression(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Build Milvus filter expression from filters dictionary

        Args:
            filters: Dictionary of filters

        Returns:
            Filter expression string or None
        """
        if not filters:
            return None

        expressions = []

        # Document ID filter
        if "document_id" in filters:
            doc_id = filters["document_id"]
            expressions.append(f'document_id == "{doc_id}"')

        # Page number filter
        if "page_number" in filters:
            page = filters["page_number"]
            if isinstance(page, list):
                page_expr = " or ".join([f"page_number == {p}" for p in page])
                expressions.append(f"({page_expr})")
            else:
                expressions.append(f"page_number == {page}")

        # Combine expressions
        if expressions:
            return " and ".join(expressions)

        return None

    def _enrich_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich results by fetching text from MinIO using stored paths

        Args:
            results: Search results from Milvus

        Returns:
            Enriched results with text from MinIO
        """
        # Collect all MinIO paths
        minio_paths = []
        for result in results:
            path = result.get("minio_object_path")
            if path:
                minio_paths.append(path)
            else:
                minio_paths.append(None)

        # Batch fetch from MinIO
        if any(minio_paths):
            valid_paths = [p for p in minio_paths if p]
            chunk_data_list = self.storage.get_chunks_batch(valid_paths)
        else:
            chunk_data_list = []

        # Map back to results
        enriched = []
        chunk_idx = 0

        for i, result in enumerate(results):
            if minio_paths[i]:
                if chunk_idx < len(chunk_data_list) and chunk_data_list[chunk_idx]:
                    # Merge MinIO data with search result
                    chunk_data = chunk_data_list[chunk_idx]
                    result["text"] = chunk_data.get("text", "")
                    result["token_count"] = chunk_data.get("token_count", 0)
                    result["char_count"] = chunk_data.get("char_count", 0)
                    # Merge additional metadata
                    if "metadata" in chunk_data:
                        if "metadata" not in result:
                            result["metadata"] = {}
                        result["metadata"].update(chunk_data["metadata"])
                chunk_idx += 1
            else:
                # No MinIO path, text should be in result already
                if "text" not in result:
                    result["text"] = ""
                    logger.warning(f"No text available for chunk {result.get('chunk_id')}")

            enriched.append(result)

        return enriched

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple text similarity (Jaccard)

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score [0, 1]
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)