"""Collection service handler for searching Milvus collections via HTTP"""

import time
import httpx
from typing import List, Optional

from app.core.orchestrator.handlers.base import BaseHandler, HandlerResult, SearchResult, SourceType
from schemas.api.requests.query import CollectionFilter
from app.config import settings


class CollectionServiceHandler(BaseHandler):
    """
    Handler for searching collections via internal HTTP endpoint

    This handler calls POST /api/collections/query endpoint,
    isolating Milvus logic from the orchestrator for clean architecture.
    """

    def __init__(self, collections: List[CollectionFilter], user_token: str, options=None):
        """
        Initialize collection service handler

        Args:
            collections: List of collection filters with scopes
            user_token: JWT token for authentication
            options: Query options for tone, citations, etc.
        """
        # Use PRIVATE as default source_type (can be overridden by actual results)
        super().__init__(SourceType.PRIVATE, system_prompt=None, options=options)
        self.collections = collections
        self.user_token = user_token

    async def search(
        self,
        question: str,
        top_k: int = 5,
        min_relevance_score: float = 0.7,
        **kwargs
    ) -> HandlerResult:
        """
        Search in collections via internal HTTP endpoint

        Args:
            question: User's question
            top_k: Maximum number of results
            min_relevance_score: Minimum score threshold

        Returns:
            HandlerResult with search results from collections
        """
        start_time = time.time()

        try:
            self.logger.info(f"📦 Querying collections via internal endpoint: {[c.name for c in self.collections]}")

            # Prepare request payload
            request_payload = {
                "question": question,
                "collections": [
                    {
                        "name": c.name,
                        "scopes": [s.value for s in c.scopes]
                    }
                    for c in self.collections
                ],
                "top_k": top_k,
                "min_relevance_score": min_relevance_score
            }

            # Add options if provided
            if self.options:
                request_payload["options"] = {
                    "tone": self.options.tone,
                    "lang": self.options.lang,
                    "citations": self.options.citations,
                    "stream": self.options.stream
                }

            # Call internal collections query endpoint
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://localhost:8080/api/collections/query",
                    json=request_payload,
                    headers={"Authorization": f"Bearer {self.user_token}"}
                )

            processing_time = time.time() - start_time

            if response.status_code != 200:
                # Enhanced error logging with response details
                error_msg = f"Collections query failed: HTTP {response.status_code}"

                # Try to extract error details from response
                try:
                    error_detail = response.json().get("detail", "No details available")
                    if response.status_code == 404:
                        self.logger.warning(f"⚠️ {error_msg} - Collection not found: {error_detail}")
                        error_msg = f"Collection not found: {error_detail}"
                    else:
                        self.logger.warning(f"⚠️ {error_msg} - {error_detail}")
                        error_msg = f"{error_msg} - {error_detail}"
                except Exception:
                    self.logger.warning(f"⚠️ {error_msg}")

                return self._create_error_result(error_msg)

            # Parse response
            response_data = response.json()

            if not response_data.get("success"):
                # Enhanced logging for success=false
                error_msg = "Collections query returned success=false"

                # Try to extract additional error info
                collections_searched = response_data.get("collections_searched", 0)
                total_results = response_data.get("total_results", 0)

                self.logger.warning(f"⚠️ {error_msg} (collections_searched={collections_searched}, total_results={total_results})")

                # If no collections were searched, it means they don't exist
                if collections_searched == 0:
                    error_msg = "No collections found - they may not exist or user doesn't have access"

                return self._create_error_result(error_msg)

            # Extract results
            collection_results = response_data.get("results", [])
            generated_answer = response_data.get("generated_answer")

            self.logger.info(f"✅ Collections query returned {len(collection_results)} results")

            # Convert to SearchResult objects
            search_results = []
            for result_data in collection_results:
                search_result = self._convert_collection_result(result_data)
                if search_result:
                    search_results.append(search_result)

            return self._create_success_result(
                results=search_results,
                processing_time=processing_time,
                generated_answer=generated_answer
            )

        except Exception as e:
            self.logger.error(f"❌ Collection service error: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_error_result(str(e))

    def _convert_collection_result(self, result_data: dict) -> Optional[SearchResult]:
        """Convert collection query result to SearchResult object"""
        try:
            # Determine source type from result
            source_type_str = result_data.get("source_type", "private")
            source_type = SourceType.PRIVATE if source_type_str == "private" else SourceType.SHARED

            return SearchResult(
                score=result_data.get("score", 0.0),
                document_id=result_data.get("document_id", "unknown"),
                text=result_data.get("text", ""),
                source_type=source_type,
                metadata=result_data.get("metadata", {}),
                chunk_index=result_data.get("chunk_index", 0),
                page_number=result_data.get("page_number", 0),
                document_title=result_data.get("document_title", "Unknown"),
                created_at=result_data.get("metadata", {}).get("created_at", 0)
            )

        except Exception as e:
            self.logger.error(f"Error converting collection result: {e}")
            return None
