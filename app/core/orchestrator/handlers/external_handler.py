"""External service handler for MEVZUAT and KARAR sources"""

import time
from typing import Optional

from app.core.orchestrator.handlers.base import BaseHandler, HandlerResult, SearchResult, SourceType
from app.services.global_db_service import get_global_db_client
from schemas.api.requests.scope import ScopeIdentifier

# Source name to MinIO bucket/Milvus collection base name mapping
# Maps user-friendly names to actual bucket names in Global DB service
SOURCE_TO_BUCKET_MAPPING = {
    "Türk Hukuku Mevzuatları": "mevzuat",
    "Türk Hukuku Kararları": "kararlar",
    "Reklam Kurulu Kararları": "reklam_kurulu_kararlari",
    # Add more mappings as needed
}


class ExternalServiceHandler(BaseHandler):
    """
    Handler for searching external Global DB service

    Note: This handler doesn't use local prompt because the external
    Global DB service generates answers with its own prompts.
    """

    def __init__(self, source_path: str, user_access_token: str, options=None):
        """
        Initialize external service handler

        Args:
            source_path: Source path for Global DB (e.g., "Türk Hukuku Mevzuatları", "mevzuat", "karar")
                        Can contain Turkish characters and spaces (will be mapped to bucket names)
            user_access_token: JWT access token for authentication
            options: Query options for tone, citations, etc.
        """
        # No system_prompt needed - external service generates its own answer
        super().__init__(SourceType.EXTERNAL, system_prompt=None, options=options)
        self.user_access_token = user_access_token
        self.source_path_original = source_path  # Keep original for logging

        # Determine bucket name:
        # 1. Check if source_path exists in mapping
        # 2. If not found, sanitize the source_path for Milvus compatibility
        if source_path in SOURCE_TO_BUCKET_MAPPING:
            self.bucket_name = SOURCE_TO_BUCKET_MAPPING[source_path]
            self.logger.info(f"  🗺️ Mapped source '{source_path}' to bucket '{self.bucket_name}'")
        else:
            # Fallback: sanitize the source path (remove Turkish chars, spaces, etc.)
            self.bucket_name = ScopeIdentifier._sanitize_collection_name(source_path)
            self.logger.info(f"  🔄 No mapping found, using sanitized name: '{self.bucket_name}'")

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
            self.logger.info(f"🌍 Querying Global DB service (source: {self.source_path_original}) with options: tone={self.options.tone}, citations={self.options.citations}...")
            self.logger.info(f"  📦 Will search all active sources from Global DB")

            # Call external service with options
            # Note: Global DB service now fetches all active sources automatically via /admin/sources
            external_response = await self.global_db_client.search_public(
                question=question,
                user_token=self.user_access_token,
                top_k=top_k,
                min_relevance_score=min_relevance_score,
                options=self.options
            )

            processing_time = time.time() - start_time

            if not external_response.get("success"):
                error_msg = external_response.get("error", "Unknown error")
                self.logger.warning(f"⚠️ Global DB (source: {self.source_path_original}) query failed: {error_msg}")
                return self._create_error_result(error_msg)

            # Extract answer and citations/sources
            generated_answer = external_response.get("answer", "")
            # Try citations first (new format), fallback to sources (backward compatibility)
            external_sources = external_response.get("citations", []) or external_response.get("sources", [])

            self.logger.info(f"✅ Global DB (source: {self.source_path_original}) returned {len(external_sources)} citations")

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
            self.logger.error(f"❌ External service (source: {self.source_path_original}) error: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_error_result(str(e))

    def _convert_external_result(self, source_data: dict) -> Optional[SearchResult]:
        """Convert external service result to SearchResult object"""
        try:
            from datetime import datetime

            # Extract metadata (might be nested)
            metadata = source_data.get("metadata", {})

            # Get score (try both relevance_score and score)
            score = source_data.get("relevance_score", source_data.get("score", 0.0))

            # Get document title (try multiple field names)
            document_title = (
                source_data.get("document_name") or
                metadata.get("title") or
                metadata.get("filename") or
                "Unknown"
            )

            # Parse created_at/upload_date (might be ISO string or timestamp)
            created_at_raw = source_data.get("created_at", metadata.get("upload_date", 0))
            if isinstance(created_at_raw, str):
                # Parse ISO format string to timestamp
                try:
                    created_at = int(datetime.fromisoformat(created_at_raw.replace('Z', '+00:00')).timestamp())
                except (ValueError, AttributeError):
                    created_at = 0
            else:
                created_at = created_at_raw if isinstance(created_at_raw, int) else 0

            return SearchResult(
                score=score,
                document_id=source_data.get("document_id", "unknown"),
                text=source_data.get("text", ""),
                source_type=self.source_type,
                metadata={
                    'document_title': document_title,
                    'page_number': source_data.get("page_number", metadata.get("page_number", 0)),
                    'created_at': created_at,
                    'document_url': source_data.get("document_url", metadata.get("document_url", ""))
                },
                page_number=source_data.get("page_number", metadata.get("page_number", 0)),
                document_title=document_title,
                document_url=source_data.get("document_url", metadata.get("document_url", "#")),
                created_at=created_at
            )

        except Exception as e:
            self.logger.error(f"Error converting external result: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
