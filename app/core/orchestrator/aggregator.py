"""Result aggregator for merging multi-source search results"""

import logging
from typing import List, Dict, Optional
from urllib.parse import quote
from openai import OpenAI

from app.core.orchestrator.handlers.base import HandlerResult, SearchResult, SourceType
from schemas.api.requests.query import QueryRequest
from schemas.api.responses.query import QueryResponse, QuerySource
from app.config import settings
from app.core.storage import storage
from app.core.auth import UserContext
from app.services.auth_service import get_auth_service_client

logger = logging.getLogger(__name__)


class ResultAggregator:
    """Aggregates results from multiple handlers and generates final response"""

    def __init__(self):
        self.doc_metadata_cache = {}

    async def aggregate_and_generate(
        self,
        handler_results: List[HandlerResult],
        request: QueryRequest,
        user: UserContext,
        processing_time: float
    ) -> QueryResponse:
        """
        Aggregate results from all handlers and generate answer

        Args:
            handler_results: Results from all handlers
            request: Original query request
            user: User context
            processing_time: Total processing time

        Returns:
            QueryResponse with aggregated results and generated answer
        """
        try:
            # 1. Merge all search results
            all_results = []
            external_answers = {}

            for handler_result in handler_results:
                if not handler_result.success:
                    logger.warning(f"Handler {handler_result.source_type} failed: {handler_result.error}")
                    continue

                # Collect results
                all_results.extend(handler_result.results)

                # Collect external answers
                if handler_result.generated_answer:
                    external_answers[handler_result.source_type.value] = handler_result.generated_answer

            # 2. Sort by score and limit
            all_results.sort(key=lambda x: x.score, reverse=True)
            all_results = all_results[:request.top_k]

            # Check if we have any results
            if not all_results and not external_answers:
                return self._create_empty_response(request, user, processing_time)

            # 3. Convert to QuerySource objects and filter by relevance
            high_confidence_sources = []
            low_confidence_sources = []
            context_parts = []

            for i, result in enumerate(all_results):
                # Create QuerySource
                source = self._create_query_source(result, i + 1)

                # Filter by relevance score
                if result.score >= request.min_relevance_score:
                    high_confidence_sources.append(source)

                    # Add to context (limited by max_sources_in_context)
                    if len(high_confidence_sources) <= request.max_sources_in_context:
                        context_parts.append(
                            f"[Kaynak {len(high_confidence_sources)} - Sayfa {result.page_number}]: {result.text}"
                        )
                else:
                    # Low confidence source
                    if request.include_low_confidence_sources:
                        low_confidence_sources.append(source)

            # 4. Generate answer
            answer, model_used, tokens_used = await self._generate_answer(
                context_parts=context_parts,
                high_confidence_sources=high_confidence_sources,
                external_answers=external_answers,
                request=request
            )

            # 5. Report usage to auth service
            remaining_credits = await self._report_usage(
                user=user,
                tokens_used=tokens_used,
                processing_time=processing_time,
                request=request,
                high_confidence_sources=high_confidence_sources,
                model_used=model_used
            )

            # 6. Log summary
            logger.info(
                f"Query completed in {processing_time:.2f}s | "
                f"Retrieved: {len(all_results)} | "
                f"High confidence: {len(high_confidence_sources)} | "
                f"Low confidence: {len(low_confidence_sources)} | "
                f"Threshold: {request.min_relevance_score}"
            )

            # 7. Return response
            return QueryResponse(
                answer=answer,
                sources=high_confidence_sources,
                processing_time=processing_time,
                model_used=model_used,
                tokens_used=tokens_used,
                remaining_credits=remaining_credits,
                total_sources_retrieved=len(all_results),
                sources_after_filtering=len(high_confidence_sources),
                min_score_applied=request.min_relevance_score,
                low_confidence_sources=low_confidence_sources if request.include_low_confidence_sources else None
            )

        except Exception as e:
            logger.error(f"Aggregation error: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _create_query_source(self, result: SearchResult, rank: int) -> QuerySource:
        """Convert SearchResult to QuerySource"""

        # Handle document URL based on source type
        if result.source_type in [SourceType.MEVZUAT, SourceType.KARAR]:
            # External source - use URL from metadata
            document_url = result.document_url
            original_filename = result.document_title if result.document_title != 'Unknown' else f'{result.source_type.value.capitalize()} Document'
            doc_title = result.document_title
        else:
            # Internal source (private/shared) - generate MinIO URL
            doc_id = result.document_id

            # Try to get metadata from MinIO
            if doc_id not in self.doc_metadata_cache:
                self.doc_metadata_cache[doc_id] = storage.get_document_metadata(doc_id)

            # Determine filename
            if result.document_title and result.document_title != 'Unknown':
                original_filename = f"{result.document_title}.pdf" if not result.document_title.endswith('.pdf') else result.document_title
            elif doc_id in self.doc_metadata_cache:
                original_filename = self.doc_metadata_cache[doc_id].get("original_filename", f'{doc_id}.pdf')
            else:
                original_filename = f'{doc_id}.pdf'

            doc_title = result.document_title if result.document_title != 'Unknown' else original_filename.replace('.pdf', '')

            # Generate MinIO URL
            encoded_filename = quote(original_filename)
            document_url = f"http://localhost:9001/browser/raw-documents/{doc_id}/{encoded_filename}"

        return QuerySource(
            rank=rank,
            score=round(result.score, 3),
            document_id=result.document_id,
            document_name=original_filename,
            document_title=doc_title,
            document_url=document_url,
            page_number=result.page_number,
            text_preview=result.text[:200] + "..." if len(result.text) > 200 else result.text,
            created_at=result.created_at
        )

    async def _generate_answer(
        self,
        context_parts: List[str],
        high_confidence_sources: List[QuerySource],
        external_answers: Dict[str, str],
        request: QueryRequest
    ) -> tuple[str, str, int]:
        """
        Generate answer based on sources and context

        Returns:
            (answer, model_used, tokens_used)
        """
        # Strategy 1: Single external source - use its answer
        if len(external_answers) == 1 and len(request.sources) == 1:
            source_type = list(external_answers.keys())[0]
            answer = external_answers[source_type]
            model_used = f"OneDocs Global DB ({source_type})"
            tokens_used = 0
            logger.info(f"✅ Using answer from Global DB service ({source_type})")
            return answer, model_used, tokens_used

        # Strategy 2: Generate answer with OpenAI
        if high_confidence_sources:
            context = "\n\n".join(context_parts)
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            chat_response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Sen yardımsever bir RAG (Retrieval-Augmented Generation) asistanısın.

GÖREVİN:
• Verilen kaynak belgelerden faydalanarak soruları net ve anlaşılır şekilde cevaplamak
• Cevaplarını Türkçe dilbilgisi kurallarına uygun, akıcı bir dille yazmak
• Her zaman kaynak numaralarını belirtmek (Örn: [Kaynak 1], [Kaynak 2-3])

CEVAP FORMATI:
1. Soruya doğrudan ve özlü bir cevap ver
2. Gerekirse madde madde veya paragraflar halinde açıkla
3. Her bilgi için hangi kaynaktan alındığını belirt
4. Eğer sorunun cevabı kaynak belgelerde yoksa, "Sağlanan kaynaklarda bu soruya ilişkin bilgi bulunmamaktadır" de

ÖNEMLI:
• Sadece verilen kaynaklardaki bilgileri kullan
• Kendi bilgini ekleme, sadece kaynakları yorumla
• Belirsizlik varsa bunu belirt"""
                    },
                    {
                        "role": "user",
                        "content": f"""Kaynak Belgeler:
{context}

Soru: {request.question}

Lütfen bu soruya kaynak belgelere dayanarak cevap ver ve hangi kaynak(lardan) bilgi aldığını belirt."""
                    }
                ],
                max_tokens=500
            )

            answer = chat_response.choices[0].message.content
            model_used = settings.OPENAI_MODEL
            tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0
            return answer, model_used, tokens_used

        # Strategy 3: No sources found
        answer = "İlgili bilgi bulunamadı. Lütfen sorunuzu farklı şekilde ifade etmeyi deneyin."
        model_used = settings.OPENAI_MODEL
        tokens_used = 0
        return answer, model_used, tokens_used

    async def _report_usage(
        self,
        user: UserContext,
        tokens_used: int,
        processing_time: float,
        request: QueryRequest,
        high_confidence_sources: List[QuerySource],
        model_used: str
    ) -> int:
        """Report usage to auth service and return remaining credits"""
        auth_client = get_auth_service_client()
        remaining_credits = user.remaining_credits

        logger.info(f"[CONSUME] Starting usage reporting to auth service")
        logger.info(f"[CONSUME] User ID: {user.user_id}")
        logger.info(f"[CONSUME] Service Type: rag_query")
        logger.info(f"[CONSUME] Tokens Used: {tokens_used}")
        logger.info(f"[CONSUME] Processing Time: {processing_time:.2f}s")

        try:
            usage_result = await auth_client.consume_usage(
                user_id=user.user_id,
                service_type="rag_query",
                tokens_used=tokens_used,
                processing_time=processing_time,
                metadata={
                    "question_length": len(request.question),
                    "sources_count": len(high_confidence_sources),
                    "model": model_used,
                    "top_k": request.top_k,
                    "min_relevance_score": request.min_relevance_score
                }
            )

            logger.info(f"[CONSUME] ✅ Auth service response: {usage_result}")

            if usage_result.get("remaining_credits") is not None:
                remaining_credits = usage_result.get("remaining_credits")
                logger.info(f"[CONSUME] Updated remaining credits: {remaining_credits}")

        except Exception as e:
            logger.error(f"[CONSUME] ❌ Failed to report usage to auth service: {str(e)}")
            import traceback
            logger.error(f"[CONSUME] Traceback: {traceback.format_exc()}")

        return remaining_credits

    def _create_empty_response(
        self,
        request: QueryRequest,
        user: UserContext,
        processing_time: float
    ) -> QueryResponse:
        """Create empty response when no results found"""
        return QueryResponse(
            answer="İlgili bilgi bulunamadı.",
            sources=[],
            processing_time=processing_time,
            model_used=settings.OPENAI_MODEL,
            total_sources_retrieved=0,
            sources_after_filtering=0,
            min_score_applied=request.min_relevance_score,
            tokens_used=0,
            remaining_credits=user.remaining_credits
        )
