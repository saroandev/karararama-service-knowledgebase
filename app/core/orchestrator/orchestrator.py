"""Main query orchestrator for coordinating multi-source searches"""

import asyncio
import logging
import time
from typing import List

from app.core.orchestrator.handlers.base import BaseHandler, SourceType
from app.core.orchestrator.handlers.milvus_handler import MilvusSearchHandler
from app.core.orchestrator.handlers.external_handler import ExternalServiceHandler
from app.core.orchestrator.aggregator import ResultAggregator
from schemas.api.requests.query import QueryRequest, QueryOptions
from schemas.api.requests.scope import DataScope
from schemas.api.responses.query import QueryResponse
from app.core.auth import UserContext

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """
    Orchestrates multi-source query execution

    Responsibilities:
    1. Analyze requested sources
    2. Create appropriate handlers
    3. Execute handlers in parallel
    4. Aggregate results via ResultAggregator
    """

    def __init__(self):
        self.aggregator = ResultAggregator()

    async def execute_query(
        self,
        request: QueryRequest,
        user: UserContext,
        user_token: str
    ) -> QueryResponse:
        """
        Execute query across all requested sources

        Args:
            request: Query request with question and sources
            user: User context with permissions
            user_token: JWT token for external service authentication

        Returns:
            QueryResponse with aggregated results
        """
        start_time = time.time()

        try:
            logger.info(f"🎯 Orchestrator: Processing query for user {user.user_id}")
            logger.info(f"📝 Question: {request.question}")
            logger.info(f"🔍 Requested sources: {[s.value for s in request.sources]}")

            # Set default options if not provided
            options = request.options or QueryOptions()
            logger.info(f"⚙️ Query options: tone={options.tone}, citations={options.citations}, lang={options.lang}")

            # 1. Expand ALL to PRIVATE + SHARED
            expanded_sources = self._expand_sources(request.sources)
            logger.info(f"📋 Expanded sources: {[s.value for s in expanded_sources]}")

            # 2. Create handlers for each source type with options
            handlers = self._create_handlers(expanded_sources, user, user_token, options)

            if not handlers:
                logger.warning("⚠️ No handlers created - no accessible sources")
                processing_time = time.time() - start_time
                return self.aggregator._create_empty_response(request, user, processing_time)

            logger.info(f"🚀 Created {len(handlers)} handlers: {[h.source_type.value for h in handlers]}")

            # 3. Execute all handlers in parallel
            logger.info("⚡ Executing handlers in parallel...")
            handler_results = await asyncio.gather(
                *[
                    handler.search(
                        question=request.question,
                        top_k=request.top_k,
                        min_relevance_score=request.min_relevance_score
                    )
                    for handler in handlers
                ],
                return_exceptions=True  # Don't fail if one handler fails
            )

            # Handle any exceptions from handlers
            safe_results = []
            for i, result in enumerate(handler_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Handler {handlers[i].source_type.value} raised exception: {result}")
                    # Create error result
                    error_result = handlers[i]._create_error_result(str(result))
                    safe_results.append(error_result)
                else:
                    safe_results.append(result)

            logger.info(f"✅ All handlers completed")
            for result in safe_results:
                logger.info(f"  - {result}")

            # 4. Aggregate results and generate answer
            processing_time = time.time() - start_time
            logger.info(f"🔄 Aggregating results...")

            response = await self.aggregator.aggregate_and_generate(
                handler_results=safe_results,
                request=request,
                user=user,
                processing_time=processing_time
            )

            logger.info(f"✅ Query orchestration completed in {processing_time:.2f}s")
            return response

        except Exception as e:
            logger.error(f"❌ Orchestrator error: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _expand_sources(self, sources: List[DataScope]) -> List[DataScope]:
        """Expand ALL to PRIVATE and SHARED, remove duplicates"""
        expanded = []

        for source in sources:
            if source == DataScope.ALL:
                # Expand ALL to both PRIVATE and SHARED
                expanded.extend([DataScope.PRIVATE, DataScope.SHARED])
            else:
                expanded.append(source)

        # Remove duplicates while preserving order
        seen = set()
        unique_sources = []
        for source in expanded:
            if source not in seen:
                seen.add(source)
                unique_sources.append(source)

        return unique_sources

    def _create_handlers(
        self,
        sources: List[DataScope],
        user: UserContext,
        user_token: str,
        options: QueryOptions
    ) -> List[BaseHandler]:
        """Create handlers for requested sources with query options"""
        handlers = []

        # Group Milvus sources (PRIVATE, SHARED)
        milvus_sources = [s for s in sources if s in [DataScope.PRIVATE, DataScope.SHARED]]
        if milvus_sources:
            logger.info(f"📦 Creating Milvus handler for: {[s.value for s in milvus_sources]}")
            handlers.append(
                MilvusSearchHandler(
                    user=user,
                    scopes=milvus_sources,
                    options=options
                )
            )

        # Create handler for MEVZUAT
        if DataScope.MEVZUAT in sources:
            logger.info("📜 Creating MEVZUAT handler")
            handlers.append(
                ExternalServiceHandler(
                    source_type=SourceType.MEVZUAT,
                    user_token=user_token,
                    bucket="mevzuat",
                    options=options
                )
            )

        # Create handler for KARAR
        if DataScope.KARAR in sources:
            logger.info("⚖️ Creating KARAR handler")
            handlers.append(
                ExternalServiceHandler(
                    source_type=SourceType.KARAR,
                    user_token=user_token,
                    bucket="karar",
                    options=options
                )
            )

        return handlers
