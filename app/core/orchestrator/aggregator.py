"""Result aggregator for merging multi-source search results"""

import logging
from typing import List, Dict, Optional
from urllib.parse import quote
from openai import OpenAI

from app.core.orchestrator.handlers.base import HandlerResult, SearchResult, SourceType
from app.core.orchestrator.prompts import PromptTemplate
from app.core.conversation import conversation_manager
from schemas.api.requests.query import QueryRequest, QueryOptions
from schemas.api.responses.query import QueryResponse, QuerySource
from app.config import settings
from app.config.constants import ServiceType
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
        processing_time: float,
        conversation_id: str
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
            # 1. Merge all search results and track failures
            all_results = []
            failed_handlers = []

            for handler_result in handler_results:
                if not handler_result.success:
                    logger.warning(f"Handler {handler_result.source_type} failed: {handler_result.error}")
                    failed_handlers.append({
                        "source_type": handler_result.source_type.value,
                        "error": handler_result.error
                    })
                    continue

                # Collect results
                all_results.extend(handler_result.results)

            # 2. Sort by score and limit
            all_results.sort(key=lambda x: x.score, reverse=True)
            all_results = all_results[:request.top_k]

            # Check if we have any results or answers
            has_any_answer = any(r.success and r.generated_answer for r in handler_results)
            if not all_results and not has_any_answer:
                return self._create_empty_response(request, user, processing_time, conversation_id)

            # Get options (default if not provided)
            options = request.options or QueryOptions()

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
                        # Include citations based on options
                        if options.citations:
                            context_parts.append(
                                f"[Kaynak {len(high_confidence_sources)} - Sayfa {result.page_number}]: {result.text}"
                            )
                        else:
                            # No citation markers
                            context_parts.append(result.text)
                else:
                    # Low confidence source
                    if request.include_low_confidence_sources:
                        low_confidence_sources.append(source)

            # 4. Generate answer (or synthesize from handler answers)
            answer, model_used, tokens_used = await self._generate_answer(
                context_parts=context_parts,
                high_confidence_sources=high_confidence_sources,
                handler_results=handler_results,
                request=request,
                user=user,
                conversation_id=conversation_id
            )

            # 4.5. Add partial failure warning if some handlers failed but we have results
            if failed_handlers and answer:
                options = request.options or QueryOptions()
                lang = options.lang if options.lang else "tr"
                failure_notice = self._build_failure_notice(failed_handlers, lang)
                answer = f"{answer}\n\n{failure_notice}"
                logger.info(f"⚠️ Added partial failure notice for {len(failed_handlers)} failed handler(s)")

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
                f"Threshold: {request.min_relevance_score} | "
                f"Citations: {options.citations}"
            )

            # 7. Apply citations control to response
            # If citations=false, return empty sources array (user wants clean answer only)
            final_sources = high_confidence_sources if options.citations else []
            final_low_confidence = low_confidence_sources if (options.citations and request.include_low_confidence_sources) else None

            logger.info(f"📋 Returning {len(final_sources)} sources (citations={options.citations})")

            # 8. Save assistant answer to conversation log
            conversation_manager.save_message(
                conversation_id=conversation_id,
                user_id=user.user_id,
                organization_id=user.organization_id,
                role="assistant",
                content=answer,
                sources=[source.dict() for source in final_sources],
                tokens_used=tokens_used,
                processing_time=processing_time
            )
            logger.info(f"💾 Saved assistant answer to conversation log")

            # 9. Return response
            return QueryResponse(
                answer=answer,
                conversation_id=conversation_id,
                citations=final_sources,
                processing_time=processing_time,
                model_used=model_used,
                tokens_used=tokens_used,
                remaining_credits=remaining_credits,
                total_sources_retrieved=len(all_results),
                sources_after_filtering=len(high_confidence_sources),
                min_score_applied=request.min_relevance_score,
                low_confidence_citations=final_low_confidence
            )

        except Exception as e:
            logger.error(f"Aggregation error: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _create_query_source(self, result: SearchResult, rank: int) -> QuerySource:
        """Convert SearchResult to QuerySource"""

        # Handle document URL based on source type
        if result.source_type == SourceType.EXTERNAL:
            # External source - use URL from metadata
            document_url = result.document_url
            original_filename = result.document_title if result.document_title != 'Unknown' else 'External Document'
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
        handler_results: List[HandlerResult],
        request: QueryRequest,
        user: UserContext,
        conversation_id: str
    ) -> tuple[str, str, int]:
        """
        Generate final answer from handler-generated answers

        Each handler now generates its own answer with scope-specific prompts.
        This method either:
        1. Returns single handler's answer (if only one source)
        2. Synthesizes multiple answers into meta-answer (if multiple sources)

        Returns:
            (answer, model_used, tokens_used)
        """
        # Collect all generated answers from handlers
        handler_answers = {}
        for result in handler_results:
            if result.success and result.generated_answer:
                handler_answers[result.source_type.value] = result.generated_answer

        # Strategy 1: Single source - use its answer directly
        if len(handler_answers) == 1:
            source_type = list(handler_answers.keys())[0]
            answer = handler_answers[source_type]
            model_used = f"Handler: {source_type}"
            tokens_used = 0
            logger.info(f"✅ Using answer from single source: {source_type}")
            return answer, model_used, tokens_used

        # Strategy 2: Multiple sources - synthesize answers
        if len(handler_answers) > 1:
            # Get options for synthesis
            options = request.options or QueryOptions()

            answer, tokens_used = await self._synthesize_answers(
                answers=handler_answers,
                question=request.question,
                options=options,
                user=user,
                conversation_id=conversation_id
            )
            model_used = f"{settings.OPENAI_MODEL} (meta-synthesis)"
            logger.info(f"✅ Synthesized answer from {len(handler_answers)} sources")
            return answer, model_used, tokens_used

        # Strategy 3: No answers generated - fallback
        answer = "İlgili bilgi bulunamadı. Lütfen sorunuzu farklı şekilde ifade etmeyi deneyin."
        model_used = settings.OPENAI_MODEL
        tokens_used = 0
        logger.warning("⚠️ No answers generated from any handler")
        return answer, model_used, tokens_used

    async def _synthesize_answers(
        self,
        answers: Dict[str, str],
        question: str,
        options: QueryOptions,
        user: UserContext,
        conversation_id: str
    ) -> tuple[str, int]:
        """
        Synthesize multiple scope-specific answers into a comprehensive meta-answer

        Args:
            answers: Dict mapping source_type to generated answer
            question: Original user question
            options: Query options for tone, citations, etc.
            user: User context
            conversation_id: Conversation ID for history

        Returns:
            (synthesized_answer, tokens_used)
        """
        # Prepare combined answers text with emoji labels
        source_emojis = {
            "private": "📄",
            "shared": "🏢",
            "external": "🌍"
        }

        combined_text = []
        for source_type, answer in answers.items():
            emoji = source_emojis.get(source_type, "📌")
            source_label = {
                "private": "Kişisel Belgelerinize Göre",
                "shared": "Organizasyon Belgelerine Göre",
                "external": "Harici Kaynaklara Göre"
            }.get(source_type, source_type.capitalize())

            combined_text.append(f"{emoji} {source_label}:\n{answer}")

        combined_answers = "\n\n---\n\n".join(combined_text)

        try:
            # Apply tone modification to synthesis prompt
            synthesis_prompt = PromptTemplate.META_SYNTHESIS

            # Add tone modifier if not default (resmi)
            if options.tone != "resmi":
                tone_modifiers = {
                    "samimi": "\n\nYou are a friendly assistant that provides casual and approachable answers based on provided sources. Use a conversational and warm tone.\n\nTONE: Use CASUAL and FRIENDLY language. Be conversational, warm, and approachable as if talking to a friend.",
                    "teknik": "\n\nYou are a legal-technical expert that provides detailed, accurate, and terminology-rich answers based on provided legal sources. Use field-specific terminology, cite definitions precisely, and include analytical explanations when relevant.\n\nTONE: Use TECHNICAL and DETAILED language. Include specific legal or regulatory terms, cite definitions when necessary, and provide methodical, data-supported reasoning.",
                    "öğretici": "\n\nYou are an instructive legal assistant that explains legal concepts in a clear, accessible, and educational tone. Your goal is to help the reader understand the reasoning behind the legal provisions and their practical implications.\n\nTONE: Use INSTRUCTIVE and EXPLANATORY language. Explain the reasoning behind rules, give examples, and guide the user toward understanding without oversimplifying the legal meaning."
                }
                modifier = tone_modifiers.get(options.tone, "")
                synthesis_prompt += modifier

            # Add language instruction - make it VERY strong
            language_modifiers = {
                "tr": "\n\n⚠️ ÇOK ÖNEMLİ - DİL: Tüm yanıtını MUTLAKA TÜRKÇE olarak ver. Her cümleyi, her kelimeyi Türkçe yaz. İngilizce kelime kullanma.",
                "eng": "\n\n⚠️ CRITICAL - LANGUAGE: You MUST respond ENTIRELY in ENGLISH. Every sentence, every word must be in English. Do NOT use Turkish words."
            }
            lang_modifier = language_modifiers.get(options.lang, language_modifiers["tr"])
            synthesis_prompt += lang_modifier

            # Prepare user message based on language
            if options.lang == "eng":
                user_message = f"""Answers from different sources:

{combined_answers}

Question: {question}

Combine, compare and create a comprehensive response from these answers."""
            else:
                user_message = f"""Farklı kaynaklardan gelen cevaplar:

{combined_answers}

Soru: {question}

Bu cevapları birleştir, karşılaştır ve kapsamlı bir yanıt oluştur."""

            # Get conversation history
            conversation_history = conversation_manager.get_context_for_llm(
                conversation_id=conversation_id,
                user_id=user.user_id,
                organization_id=user.organization_id,
                max_messages=10
            )
            logger.info(f"📜 Retrieved {len(conversation_history)} messages from conversation history for synthesis")

            # Build messages: system + history (excluding current question as it's already in user_message)
            messages = [{"role": "system", "content": synthesis_prompt}]

            # Add history except the last user message (which is the current question)
            if conversation_history:
                messages.extend(conversation_history[:-1])  # Exclude last message (current question)

            # Add current synthesis request
            messages.append({"role": "user", "content": user_message})

            # Generate meta-synthesis with OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            chat_response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                # max_tokens=700,  # REMOVED: Let LLM decide response length based on content from handlers
                temperature=0.7
            )

            synthesized_answer = chat_response.choices[0].message.content
            tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0

            return synthesized_answer, tokens_used

        except Exception as e:
            logger.error(f"❌ Failed to synthesize answers: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Enhanced fallback: structured presentation instead of raw concatenation
            if options.lang == "eng":
                fallback_parts = [
                    "⚠️ Note: Automatic synthesis failed. Below are the individual answers from each source:\n"
                ]
            else:
                fallback_parts = [
                    "⚠️ Not: Otomatik birleştirme başarısız oldu. Aşağıda her kaynaktan gelen cevaplar ayrı ayrı sunulmuştur:\n"
                ]

            # Add each answer with clear separation
            for source_type, answer in answers.items():
                emoji = source_emojis.get(source_type, "📌")
                source_label = {
                    "private": "Kişisel Belgelerinize Göre" if options.lang == "tr" else "Based on Your Personal Documents",
                    "shared": "Organizasyon Belgelerine Göre" if options.lang == "tr" else "Based on Organization Documents",
                    "external": "Harici Kaynaklara Göre" if options.lang == "tr" else "Based on External Sources"
                }.get(source_type, source_type.capitalize())

                fallback_parts.append(f"\n{emoji} {source_label}:")
                fallback_parts.append(f"{answer}\n")
                fallback_parts.append("---")

            return "\n".join(fallback_parts), 0

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
        logger.info(f"[CONSUME] Service Type: {ServiceType.QUERY}")
        logger.info(f"[CONSUME] Tokens Used: {tokens_used}")
        logger.info(f"[CONSUME] Processing Time: {processing_time:.2f}s")

        try:
            usage_result = await auth_client.consume_usage(
                user_id=user.user_id,
                service_type=ServiceType.QUERY,
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
            # Don't fail the query if usage tracking fails
            # Just log a warning and continue with original credits
            logger.warning(f"[CONSUME] ⚠️ Usage tracking skipped: {str(e)}")

        return remaining_credits

    def _create_empty_response(
        self,
        request: QueryRequest,
        user: UserContext,
        processing_time: float,
        conversation_id: str
    ) -> QueryResponse:
        """
        Create detailed empty response when no results found

        Provides helpful context about where search was performed and actionable suggestions

        Args:
            conversation_id: Required conversation ID from request (always provided by client)
        """

        # Get language preference
        options = request.options or QueryOptions()
        lang = options.lang if options.lang else "tr"

        # Build detailed answer with context
        answer = self._build_empty_response_message(request, lang)

        # Save to conversation history (even empty responses should be logged)
        conversation_manager.save_message(
            conversation_id=conversation_id,
            user_id=user.user_id,
            organization_id=user.organization_id,
            role="assistant",
            content=answer,
            sources=[],
            tokens_used=0,
            processing_time=processing_time
        )
        logger.info(f"💾 Saved empty response to conversation log")

        return QueryResponse(
            answer=answer,
            conversation_id=conversation_id,
            citations=[],
            processing_time=processing_time,
            model_used=settings.OPENAI_MODEL,
            total_sources_retrieved=0,
            sources_after_filtering=0,
            min_score_applied=request.min_relevance_score,
            tokens_used=0,
            remaining_credits=user.remaining_credits
        )

    def _build_empty_response_message(self, request: QueryRequest, lang: str) -> str:
        """
        Build a detailed, helpful message when no results are found

        Args:
            request: Original query request
            lang: Language code (tr/eng)

        Returns:
            Detailed error message with context and suggestions
        """
        # Determine what was searched
        searched_locations = []

        # Check collections
        if request.collections:
            for coll in request.collections:
                for scope in coll.scopes:
                    if lang == "eng":
                        scope_label = "your documents" if scope.value == "private" else "organization documents"
                        searched_locations.append(f"{coll.name} collection ({scope_label})")
                    else:
                        scope_label = "kişisel belgeleriniz" if scope.value == "private" else "organizasyon belgeleri"
                        searched_locations.append(f"{coll.name} koleksiyonu ({scope_label})")

        # Check external sources
        if request.sources:
            for source in request.sources:
                if lang == "eng":
                    source_labels = {
                        "mevzuat": "Legislation database",
                        "karar": "Court decisions database",
                        "all": "All external databases"
                    }
                    searched_locations.append(source_labels.get(source, f"{source} database"))
                else:
                    source_labels = {
                        "mevzuat": "Mevzuat veritabanı",
                        "karar": "Karar veritabanı",
                        "all": "Tüm harici veritabanları"
                    }
                    searched_locations.append(source_labels.get(source, f"{source} veritabanı"))

        # Build message based on language
        if lang == "eng":
            parts = ["No relevant information found."]

            if searched_locations:
                parts.append("\n🔍 Searched in:")
                for loc in searched_locations:
                    parts.append(f"  • {loc}")

            parts.append("\n💡 Suggestions:")
            parts.append("  • Try rephrasing your question with different terms")
            parts.append("  • Use more general or specific keywords")

            if request.collections:
                parts.append("  • Check if your collections contain relevant documents")
            else:
                parts.append("  • Try searching in specific collections")

            if request.min_relevance_score > 0.7:
                parts.append(f"  • Lower the relevance threshold (currently {request.min_relevance_score})")

            return "\n".join(parts)

        else:  # Turkish
            parts = ["İlgili bilgi bulunamadı."]

            if searched_locations:
                parts.append("\n🔍 Arama Yapılan Yerler:")
                for loc in searched_locations:
                    parts.append(f"  • {loc}")

            parts.append("\n💡 Öneriler:")
            parts.append("  • Sorunuzu farklı kelimelerle ifade etmeyi deneyin")
            parts.append("  • Daha genel veya daha spesifik terimler kullanın")

            if request.collections:
                parts.append("  • Koleksiyonlarınızda ilgili döküman olup olmadığını kontrol edin")
            else:
                parts.append("  • Belirli koleksiyonlarda arama yapmayı deneyin")

            if request.min_relevance_score > 0.7:
                parts.append(f"  • Eşleşme eşiğini düşürün (şu an {request.min_relevance_score})")

            return "\n".join(parts)

    def _build_failure_notice(self, failed_handlers: List[Dict], lang: str) -> str:
        """
        Build a notice about failed handlers for partial success scenarios

        Args:
            failed_handlers: List of failed handler info dicts
            lang: Language code (tr/eng)

        Returns:
            Formatted failure notice string
        """
        # Map source types to user-friendly names
        source_names_tr = {
            "private": "Kişisel belgeler",
            "shared": "Organizasyon belgeleri",
            "external": "Harici kaynaklar"
        }

        source_names_eng = {
            "private": "Your personal documents",
            "shared": "Organization documents",
            "external": "External sources"
        }

        if lang == "eng":
            parts = ["\n---\n", "⚠️ Note: Some sources could not be accessed:"]
            for failure in failed_handlers:
                source_name = source_names_eng.get(failure["source_type"], failure["source_type"])
                # Simplify error message for user
                error_msg = self._simplify_error_message(failure["error"], lang)
                parts.append(f"  • {source_name}: {error_msg}")
            parts.append("\nThe answer above was provided based on available sources only.")
            return "\n".join(parts)

        else:  # Turkish
            parts = ["\n---\n", "⚠️ Not: Bazı kaynaklara erişilemedi:"]
            for failure in failed_handlers:
                source_name = source_names_tr.get(failure["source_type"], failure["source_type"])
                # Simplify error message for user
                error_msg = self._simplify_error_message(failure["error"], lang)
                parts.append(f"  • {source_name}: {error_msg}")
            parts.append("\nYukarıdaki cevap sadece erişilebilen kaynaklara göre verilmiştir.")
            return "\n".join(parts)

    def _simplify_error_message(self, error: str, lang: str) -> str:
        """
        Convert technical error messages to user-friendly descriptions

        Args:
            error: Technical error message
            lang: Language code (tr/eng)

        Returns:
            Simplified error message
        """
        error_lower = error.lower()

        # Common error patterns and their translations
        if "timeout" in error_lower or "timed out" in error_lower:
            return "Zaman aşımı" if lang == "tr" else "Timeout"
        elif "not found" in error_lower or "404" in error_lower:
            return "Bulunamadı" if lang == "tr" else "Not found"
        elif "connection" in error_lower or "unreachable" in error_lower:
            return "Bağlantı hatası" if lang == "tr" else "Connection error"
        elif "unauthorized" in error_lower or "403" in error_lower or "401" in error_lower:
            return "Yetki hatası" if lang == "tr" else "Authorization error"
        elif "service unavailable" in error_lower or "503" in error_lower:
            return "Servis erişilemez" if lang == "tr" else "Service unavailable"
        else:
            # Generic message for unknown errors
            return "Geçici hata" if lang == "tr" else "Temporary error"
