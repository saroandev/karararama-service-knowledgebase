import logging
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import CrossEncoder

from app.index import milvus_indexer
from app.embed import embedding_generator
from app.storage import storage
from app.config import settings

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, use_reranker: bool = True):
        self.indexer = milvus_indexer
        self.embedder = embedding_generator
        self.storage = storage
        self.use_reranker = use_reranker
        
        if self.use_reranker:
            self.reranker = self._load_reranker()
    
    def _load_reranker(self) -> CrossEncoder:
        """Load the reranking model"""
        try:
            model = CrossEncoder(
                settings.RERANKER_MODEL,
                max_length=512
            )
            logger.info(f"Loaded reranker: {settings.RERANKER_MODEL}")
            return model
        except Exception as e:
            logger.error(f"Error loading reranker: {e}")
            return None
    
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_reranker: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query
        
        Args:
            query: Query text
            top_k: Number of results to return
            filters: Optional filters for search
            use_reranker: Whether to use reranker (overrides default)
        
        Returns:
            List of relevant chunks with scores
        """
        # Generate query embedding
        query_embedding = self.embedder.generate_embedding(query)
        
        # Convert filters to Milvus expression
        filter_expr = self._build_filter_expression(filters)
        
        # Initial retrieval
        if use_reranker or (use_reranker is None and self.use_reranker):
            # Retrieve more candidates for reranking
            initial_k = min(top_k * 3, 100)
        else:
            initial_k = top_k
        
        results = self.indexer.search(
            query_embedding=query_embedding,
            top_k=initial_k,
            filters=filter_expr
        )
        
        # Rerank if needed
        if (use_reranker or (use_reranker is None and self.use_reranker)) and self.reranker:
            results = self._rerank_results(query, results, top_k)
        else:
            results = results[:top_k]
        
        # Enrich results with full text from storage
        enriched_results = self._enrich_results(results)
        
        return enriched_results
    
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
    
    def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results using cross-encoder
        
        Args:
            query: Query text
            results: Initial search results
            top_k: Number of results to return
        
        Returns:
            Reranked results
        """
        if not results or not self.reranker:
            return results[:top_k]
        
        # Prepare pairs for reranking
        pairs = [[query, result["text"]] for result in results]
        
        # Get reranking scores
        try:
            scores = self.reranker.predict(pairs)
            
            # Add reranking scores to results
            for i, result in enumerate(results):
                result["rerank_score"] = float(scores[i])
                result["original_score"] = result["score"]
            
            # Sort by reranking score
            results.sort(key=lambda x: x["rerank_score"], reverse=True)
            
            logger.debug(f"Reranked {len(results)} results")
            
        except Exception as e:
            logger.error(f"Error during reranking: {e}")
        
        return results[:top_k]
    
    def _enrich_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich results with additional data from storage
        
        Args:
            results: Search results
        
        Returns:
            Enriched results
        """
        enriched = []
        
        for result in results:
            # Try to get full chunk data from storage
            chunk_data = self.storage.get_chunk(
                result["document_id"],
                result["chunk_id"].split("_")[-2] + "_" + result["chunk_id"].split("_")[-1]
            )
            
            if chunk_data:
                # Merge storage data with search result
                result.update(chunk_data)
            
            enriched.append(result)
        
        return enriched
    
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
        # Get initial candidates
        candidates = self.retrieve(query, top_k * 3, use_reranker=False)
        
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
                    # Simple text similarity (could use embeddings)
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
        semantic_results = self.retrieve(query, top_k * 2, use_reranker=False)
        
        # Keyword search (simplified BM25-like scoring)
        all_chunks = []  # Would need to implement full-text search
        
        # For now, just filter semantic results by keyword presence
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


# Singleton instance
retriever = Retriever()