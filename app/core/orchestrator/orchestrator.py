"""Main query orchestrator for coordinating multi-source searches"""

import asyncio
import logging
import time
from typing import List

from app.core.orchestrator.handlers.base import BaseHandler
from app.core.orchestrator.handlers.collection_handler import CollectionServiceHandler
from app.core.orchestrator.handlers.external_handler import ExternalServiceHandler
from app.core.orchestrator.aggregator import ResultAggregator
from app.core.conversation import conversation_manager
from schemas.api.requests.query import QueryRequest, QueryOptions
from schemas.api.responses.query import QueryResponse
from app.core.auth import UserContext
from app.config import settings

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
        user_access_token: str
    ) -> QueryResponse:
        """
        Execute query across all requested sources

        Args:
            request: Query request with question and sources
            user: User context with permissions
            user_access_token: JWT access token for authentication

        Returns:
            QueryResponse with aggregated results
        """
        start_time = time.time()

        try:
            logger.info(f"🎯 Orchestrator: Processing query for user {user.user_id}")
            logger.info(f"📝 Question: {request.question}")
            logger.info(f"🔍 Requested sources: {request.sources}")
            logger.info(f"🔍 Requested sources: {request.collections}")

            # Handle conversation history
            conversation_id = request.conversation_id or conversation_manager.create_new_conversation()
            logger.info(f"💬 Conversation ID: {conversation_id}")

            # Save user question to conversation log
            conversation_manager.save_message(
                conversation_id=conversation_id,
                user_id=user.user_id,
                organization_id=user.organization_id,
                role="user",
                content=request.question
            )
            logger.info(f"💾 Saved user question to conversation log")

            # Set default options if not provided
            options = request.options or QueryOptions()
            logger.info(f"⚙️ Query options: tone={options.tone}, citations={options.citations}, lang={options.lang}")

            # Create handlers for external sources and collection filters
            handlers = self._create_handlers(request.sources, user, user_access_token, options, request.collections)

            if not handlers:
                logger.warning("⚠️ No handlers created - falling back to LLM-only mode")
                processing_time = time.time() - start_time
                return await self._generate_llm_only_response(request, user, processing_time, conversation_id)

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
                processing_time=processing_time,
                conversation_id=conversation_id
            )

            logger.info(f"✅ Query orchestration completed in {processing_time:.2f}s")
            return response

        except Exception as e:
            logger.error(f"❌ Orchestrator error: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _create_handlers(
        self,
        sources: List[str],
        user: UserContext,
        user_access_token: str,
        options: QueryOptions,
        collection_filters = None
    ) -> List[BaseHandler]:
        """
        Create handlers for requested sources and collections

        BEHAVIOR:
        - sources: External source paths for Global DB (e.g., "mevzuat", "karar", "reklam-kurulu-kararlari", "all")
        - collections: For Milvus collection-specific search (private/shared)
        - If neither specified: LLM-only mode (no RAG)
        - Both can coexist and run in parallel

        Args:
            sources: List of external source paths (strings)
            user: User context
            user_access_token: JWT access token for authentication
            options: Query options (tone, lang, etc.)
            collection_filters: Optional list of CollectionFilter objects
        """
        handlers = []

        # 1. Create handler for COLLECTIONS (if specified)
        if collection_filters:
            logger.info(f"🗂️ Creating Collection handler: {len(collection_filters)} collection(s)")

            handlers.append(
                CollectionServiceHandler(
                    collections=collection_filters,
                    user_access_token=user_access_token,
                    options=options
                )
            )

        # 2. Create handlers for EXTERNAL SOURCES (Global DB)
        for source_path in sources:
            logger.info(f"🌍 Creating External handler for source: {source_path}")
            handlers.append(
                ExternalServiceHandler(
                    source_path=source_path,
                    user_access_token=user_access_token,
                    options=options
                )
            )

        return handlers

    async def _generate_llm_only_response(
        self,
        request: QueryRequest,
        user: UserContext,
        processing_time: float,
        conversation_id: str
    ) -> QueryResponse:
        """
        Generate LLM-only response without RAG when no sources/collections specified

        Uses OpenAI directly to answer the question based on its training data with conversation history.
        """
        from openai import OpenAI
        from app.core.orchestrator.prompts import PromptTemplate

        logger.info("🤖 No sources or collections specified - generating LLM-only response")

        try:
            # Use OpenAI to create answer
            options = request.options or QueryOptions()

            # Get base LLM-only prompt
            system_prompt = PromptTemplate.LLM_ONLY

            # Apply tone modifier if specified and different from default
            if options.tone and options.tone != "resmi":
                tone_modifier = PromptTemplate.TONE_MODIFIERS.get(options.tone, "")
                if tone_modifier:
                    system_prompt += tone_modifier
                    logger.info(f"🎨 Applied tone modifier: {options.tone}")

            # Apply language modifier if English
            if options.lang == "eng":
                # Override with English version
                system_prompt = (
                    "You are a helpful AI assistant.\n\n"
                    "YOUR TASK:\n"
                    "• Answer user questions based on your general knowledge and training data\n"
                    "• Provide accurate, current, and helpful information\n"
                    "• Write clearly, understandably, and naturally\n"
                    "• Explicitly state when uncertain\n\n"
                    "ANSWER STYLE:\n"
                    "• Give direct and concise answers\n"
                    "• Break down into bullet points when needed\n"
                    "• Explain complex topics in simple language\n"
                    "• Use examples to make topics concrete\n\n"
                    "IMPORTANT RULES:\n"
                    "• Answer only based on your own knowledge and training data\n"
                    "• Do not reference specific sources (since no documents were provided)\n"
                    "• Say \"I don't have definite knowledge about this\" when unsure\n"
                    "• Don't speculate, admit when you don't know\n"
                    "• For current events, note \"My training data is up to early 2024\"\n\n"
                    "NOTE:\n"
                    "The user has not provided any documents, so you should answer using only your general knowledge."
                )
                # Apply tone modifier for English as well
                if options.tone and options.tone != "resmi":
                    tone_modifier = PromptTemplate.TONE_MODIFIERS.get(options.tone, "")
                    if tone_modifier:
                        system_prompt += tone_modifier
                logger.info(f"🌍 Using English language prompt")

            # Get conversation history
            conversation_history = conversation_manager.get_context_for_llm(
                conversation_id=conversation_id,
                user_id=user.user_id,
                organization_id=user.organization_id,
                max_messages=10
            )
            logger.info(f"📜 Retrieved {len(conversation_history)} messages from conversation history")

            # Build messages: system + history + current question
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation_history)

            # Call OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            chat_response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                max_tokens=700,
                temperature=0.7
            )

            answer = chat_response.choices[0].message.content
            tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0
            model_used = settings.OPENAI_MODEL

            logger.info(f"✅ LLM-only response generated using {model_used} ({tokens_used} tokens)")

            # Save assistant answer to conversation log
            conversation_manager.save_message(
                conversation_id=conversation_id,
                user_id=user.user_id,
                organization_id=user.organization_id,
                role="assistant",
                content=answer,
                sources=[],
                tokens_used=tokens_used,
                processing_time=processing_time
            )

            # Create response
            return QueryResponse(
                answer=answer,
                conversation_id=conversation_id,
                citations=[],
                low_confidence_citations=None,
                processing_time=processing_time,
                model_used=f"{model_used} (LLM-only)",
                tokens_used=tokens_used,
                remaining_credits=user.remaining_credits,
                total_sources_retrieved=0,
                sources_after_filtering=0,
                min_score_applied=request.min_relevance_score
            )

        except Exception as e:
            logger.error(f"❌ LLM-only response generation failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return empty response as fallback
            return self.aggregator._create_empty_response(request, user, processing_time, conversation_id)
