"""External service handler for MEVZUAT and KARAR sources"""

import time
from typing import Optional

from app.core.orchestrator.handlers.base import BaseHandler, HandlerResult, SearchResult, SourceType
from app.services.global_db_service import get_global_db_client


class ExternalServiceHandler(BaseHandler):
    """
    Handler for searching external Global DB service (MEVZUAT, KARAR)

    Note: This handler doesn't use local prompt because the external
    Global DB service generates answers with its own prompts.
    """

    def __init__(self, source_type: SourceType, user_token: str, bucket: str):
        """
        Initialize external service handler

        Args:
            source_type: MEVZUAT or KARAR
            user_token: JWT token for authentication
            bucket: Bucket name for Global DB ("mevzuat" or "karar")
        """
        # No system_prompt needed - external service generates its own answer
        super().__init__(source_type, system_prompt=None)
        self.user_token = user_token
        self.bucket = bucket
        self.global_db_client = get_global_db_client()

    async def search(
        self,
        question: str,
        top_k: int = 5,
        min_relevance_score: float = 0.7,
        **kwargs
    ) -> HandlerResult:
        """
        Search in external Global DB service

        Args:
            question: User's question
            top_k: Maximum number of results
            min_relevance_score: Minimum score threshold

        Returns:
            HandlerResult with search results and generated answer from external service
        """
        start_time = time.time()

        try:
            icon = "📜" if self.source_type == SourceType.MEVZUAT else "⚖️"
            self.logger.info(f"{icon} Querying Global DB service ({self.bucket})...")

            # Call external service
            external_response = await self.global_db_client.search_public(
                question=question,
                user_token=self.user_token,
                top_k=top_k,
                min_relevance_score=min_relevance_score,
                bucket=self.bucket
            )

            processing_time = time.time() - start_time

            if not external_response.get("success"):
                error_msg = external_response.get("error", "Unknown error")
                self.logger.warning(f"⚠️ Global DB ({self.bucket}) query failed: {error_msg}")
                return self._create_error_result(error_msg)

            # Extract answer and sources
            generated_answer = external_response.get("answer", "")
            external_sources = external_response.get("sources", [])

            self.logger.info(f"✅ Global DB ({self.bucket}) returned {len(external_sources)} sources")

            # Convert external sources to SearchResult objects
            search_results = []
            for source in external_sources:
                search_result = self._convert_external_result(source)
                if search_result:
                    search_results.append(search_result)

            return self._create_success_result(
                results=search_results,
                processing_time=processing_time,
                generated_answer=generated_answer
            )

        except Exception as e:
            self.logger.error(f"❌ External service ({self.bucket}) error: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_error_result(str(e))

    def _convert_external_result(self, source_data: dict) -> Optional[SearchResult]:
        """Convert external service result to SearchResult object"""
        try:
            return SearchResult(
                score=source_data.get("score", 0.0),
                document_id=source_data.get("document_id", "unknown"),
                text=source_data.get("text", ""),
                source_type=self.source_type,
                metadata={
                    'document_title': source_data.get("document_name", "Unknown"),
                    'page_number': source_data.get("page_number", 0),
                    'created_at': source_data.get("created_at", 0),
                    'document_url': source_data.get("document_url", "")
                },
                page_number=source_data.get("page_number", 0),
                document_title=source_data.get("document_name", "Unknown"),
                document_url=source_data.get("document_url", "#"),
                created_at=source_data.get("created_at", 0)
            )

        except Exception as e:
            self.logger.error(f"Error converting external result: {e}")
            return None
