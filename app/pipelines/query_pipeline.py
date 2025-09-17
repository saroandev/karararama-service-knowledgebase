"""
Query processing pipeline implementation
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.pipelines.base import AbstractPipeline, PipelineResult
from app.core.retrieval import default_retriever
from app.core.generation import default_generator
from app.core.embeddings import default_embedding_generator as embedding_generator
from app.config import settings

logger = logging.getLogger(__name__)


class QueryPipeline(AbstractPipeline):
    """
    Pipeline for processing queries against the RAG system

    Stages:
    1. Generate query embedding
    2. Retrieve relevant chunks
    3. Rerank results (optional)
    4. Generate answer using LLM
    5. Format response
    """

    def __init__(self):
        super().__init__(name="QueryPipeline")

        # Initialize components
        self.retriever = default_retriever
        self.generator = default_generator
        self.embedder = embedding_generator

        # Pipeline configuration
        self.top_k = settings.QUERY_TOP_K
        self.use_reranker = settings.USE_RERANKER
        self.score_threshold = settings.QUERY_SCORE_THRESHOLD

    def validate_inputs(self, **kwargs) -> bool:
        """
        Validate query inputs

        Required kwargs:
            - question: Query text

        Optional kwargs:
            - top_k: Number of results to retrieve
            - use_reranker: Whether to use reranking
            - filters: Query filters
            - include_sources: Include source documents
        """
        if not kwargs.get('question'):
            raise ValueError("'question' is required")

        question = kwargs.get('question', '')
        if not question.strip():
            raise ValueError("'question' cannot be empty")

        # Validate optional parameters
        top_k = kwargs.get('top_k', self.top_k)
        if top_k < 1 or top_k > 100:
            raise ValueError("'top_k' must be between 1 and 100")

        return True

    async def execute(self, **kwargs) -> PipelineResult:
        """
        Execute the query pipeline

        Args:
            question: Query text
            top_k: Number of results to retrieve
            use_reranker: Whether to use reranking
            filters: Query filters dict
            include_sources: Include source documents in response
            strategy: Retrieval strategy ('default', 'diverse', 'hybrid')

        Returns:
            PipelineResult with answer and sources
        """
        try:
            # Extract parameters
            question = kwargs.get('question')
            top_k = kwargs.get('top_k', self.top_k)
            use_reranker = kwargs.get('use_reranker', self.use_reranker)
            filters = kwargs.get('filters', None)
            include_sources = kwargs.get('include_sources', True)
            strategy = kwargs.get('strategy', 'default')

            # Stage 1: Retrieve relevant chunks
            self.update_progress(
                "retrieving",
                30.0,
                f"Searching for relevant documents (top_k={top_k})",
                1, 4
            )

            # Choose retrieval method based on strategy
            if strategy == 'diverse':
                chunks = self.retriever.retrieve_diverse(
                    query=question,
                    top_k=top_k
                )
            elif strategy == 'hybrid':
                chunks = self.retriever.hybrid_search(
                    query=question,
                    top_k=top_k
                )
            else:
                chunks = self.retriever.retrieve(
                    query=question,
                    top_k=top_k,
                    filters=filters,
                    use_reranker=use_reranker
                )

            if not chunks:
                return PipelineResult(
                    success=True,
                    data={
                        "answer": "No relevant information found for your query.",
                        "sources": [],
                        "metadata": {
                            "strategy": strategy,
                            "top_k": top_k,
                            "chunks_found": 0
                        }
                    }
                )

            # Filter by score threshold
            if self.score_threshold:
                original_count = len(chunks)
                chunks = [c for c in chunks if c.get('score', 0) >= self.score_threshold]
                if original_count != len(chunks):
                    self.logger.info(f"Filtered {original_count - len(chunks)} chunks below threshold {self.score_threshold}")

            # Stage 2: Generate answer
            self.update_progress(
                "generating",
                60.0,
                f"Generating answer from {len(chunks)} relevant chunks",
                2, 4
            )

            # Prepare context chunks for generator
            context_chunks = []
            for chunk in chunks:
                context_chunks.append({
                    "text": chunk.get("text", ""),
                    "document_id": chunk.get("document_id", ""),
                    "page_number": chunk.get("page_number", 0),
                    "score": chunk.get("score", 0),
                    "metadata": chunk.get("metadata", {})
                })

            # Generate answer
            generation_result = self.generator.generate_answer(
                question=question,
                context_chunks=context_chunks,
                max_tokens=1000,
                temperature=0.1,
                include_sources=include_sources
            )

            # Stage 3: Format response
            self.update_progress(
                "formatting",
                90.0,
                "Formatting response",
                3, 4
            )

            # Prepare sources
            sources = []
            if include_sources:
                for i, chunk in enumerate(chunks[:5]):  # Limit to top 5 sources
                    sources.append({
                        "rank": i + 1,
                        "score": round(chunk.get("score", 0), 3),
                        "document_id": chunk.get("document_id", ""),
                        "page_number": chunk.get("page_number", 0),
                        "text_preview": chunk.get("text", "")[:200] + "...",
                        "metadata": chunk.get("metadata", {})
                    })

            # Return success result
            return PipelineResult(
                success=True,
                data={
                    "answer": generation_result.get("answer", ""),
                    "sources": sources,
                    "metadata": {
                        "strategy": strategy,
                        "top_k": top_k,
                        "chunks_found": len(chunks),
                        "use_reranker": use_reranker,
                        "model_used": generation_result.get("metadata", {}).get("model", "unknown"),
                        "tokens_used": generation_result.get("metadata", {}).get("total_tokens", 0)
                    }
                }
            )

        except Exception as e:
            error_msg = f"Query processing failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            return PipelineResult(
                success=False,
                error=error_msg
            )


class MultiQueryPipeline(AbstractPipeline):
    """Pipeline for processing multiple queries"""

    def __init__(self):
        super().__init__(name="MultiQueryPipeline")
        self.single_query = QueryPipeline()

    def validate_inputs(self, **kwargs) -> bool:
        """Validate multi-query inputs"""
        if not kwargs.get('questions'):
            raise ValueError("'questions' list is required")

        questions = kwargs.get('questions', [])
        if not questions:
            raise ValueError("'questions' list cannot be empty")

        for q in questions:
            if not q or not q.strip():
                raise ValueError("All questions must be non-empty")

        return True

    async def execute(self, **kwargs) -> PipelineResult:
        """
        Execute multiple queries

        Args:
            questions: List of query strings
            top_k: Number of results per query
            use_reranker: Whether to use reranking
            strategy: Retrieval strategy

        Returns:
            PipelineResult with all query results
        """
        questions = kwargs.get('questions', [])
        total_queries = len(questions)
        results = []

        # Common parameters for all queries
        query_params = {
            "top_k": kwargs.get('top_k', 5),
            "use_reranker": kwargs.get('use_reranker', False),
            "strategy": kwargs.get('strategy', 'default'),
            "include_sources": kwargs.get('include_sources', False)
        }

        for i, question in enumerate(questions):
            # Check if cancelled
            if self.is_cancelled:
                break

            # Update progress
            self.update_progress(
                "processing",
                (i / total_queries) * 90 + 10,
                f"Processing query {i+1}/{total_queries}",
                i + 1,
                total_queries
            )

            # Process single query
            query_params['question'] = question
            result = await self.single_query.run(**query_params)

            results.append({
                "question": question,
                "success": result.success,
                "answer": result.data.get("answer") if result.success else None,
                "error": result.error if not result.success else None
            })

        # Return multi-query result
        return PipelineResult(
            success=all(r['success'] for r in results),
            data={
                "total_queries": total_queries,
                "results": results
            }
        )


class ConversationalQueryPipeline(QueryPipeline):
    """
    Extended query pipeline with conversation context support
    """

    def __init__(self):
        super().__init__()
        self.name = "ConversationalQueryPipeline"
        self.conversation_history = []

    def validate_inputs(self, **kwargs) -> bool:
        """Validate conversational query inputs"""
        # Validate base query inputs
        if not super().validate_inputs(**kwargs):
            return False

        # Validate conversation context if provided
        if 'conversation_history' in kwargs:
            history = kwargs['conversation_history']
            if not isinstance(history, list):
                raise ValueError("'conversation_history' must be a list")

        return True

    async def execute(self, **kwargs) -> PipelineResult:
        """
        Execute conversational query with context

        Args:
            question: Current query
            conversation_history: List of previous Q&A pairs
            **kwargs: Other query parameters

        Returns:
            PipelineResult with contextualized answer
        """
        # Get conversation history
        history = kwargs.get('conversation_history', self.conversation_history)

        # Build context-aware query
        if history:
            # Append context to question
            context_prompt = "Previous conversation:\n"
            for h in history[-3:]:  # Last 3 exchanges
                context_prompt += f"Q: {h.get('question', '')}\n"
                context_prompt += f"A: {h.get('answer', '')}\n"
            context_prompt += f"\nCurrent question: {kwargs['question']}"

            # Update question with context
            kwargs['question'] = context_prompt

        # Execute query
        result = await super().execute(**kwargs)

        # Update conversation history if successful
        if result.success:
            self.conversation_history.append({
                "question": kwargs.get('question'),
                "answer": result.data.get('answer'),
                "timestamp": datetime.now().isoformat()
            })

        return result

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []