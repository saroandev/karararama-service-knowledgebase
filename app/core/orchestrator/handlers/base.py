"""Base handler interface for search operations"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import logging
from openai import OpenAI
from app.config import settings

if TYPE_CHECKING:
    from schemas.api.requests.query import QueryOptions

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Source type identifiers"""
    PRIVATE = "private"
    SHARED = "shared"
    MEVZUAT = "mevzuat"
    KARAR = "karar"


@dataclass
class SearchResult:
    """Single search result from any source"""
    score: float
    document_id: str
    text: str
    source_type: SourceType
    metadata: Dict[str, Any]

    # Optional fields
    chunk_index: Optional[int] = None
    page_number: Optional[int] = 0
    document_title: Optional[str] = "Unknown"
    document_url: Optional[str] = "#"
    created_at: Optional[int] = 0


@dataclass
class HandlerResult:
    """Result from a handler execution"""
    source_type: SourceType
    results: List[SearchResult]
    success: bool
    error: Optional[str] = None
    generated_answer: Optional[str] = None  # For external services that provide answers
    processing_time: float = 0.0

    def __repr__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"HandlerResult({status} {self.source_type}, {len(self.results)} results)"


class BaseHandler(ABC):
    """Abstract base class for all search handlers"""

    def __init__(
        self,
        source_type: SourceType,
        system_prompt: Optional[str] = None,
        options: Optional['QueryOptions'] = None
    ):
        self.source_type = source_type
        self.system_prompt = system_prompt
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Set default options if not provided
        if options is None:
            from schemas.api.requests.query import QueryOptions
            options = QueryOptions()
        self.options = options

    @abstractmethod
    async def search(
        self,
        question: str,
        top_k: int = 5,
        min_relevance_score: float = 0.7,
        **kwargs
    ) -> HandlerResult:
        """
        Execute search operation

        Args:
            question: User's question
            top_k: Maximum number of results to return
            min_relevance_score: Minimum score threshold
            **kwargs: Additional handler-specific parameters

        Returns:
            HandlerResult with search results
        """
        pass

    def _create_error_result(self, error_message: str) -> HandlerResult:
        """Create an error result"""
        self.logger.error(f"Handler error: {error_message}")
        return HandlerResult(
            source_type=self.source_type,
            results=[],
            success=False,
            error=error_message
        )

    def _create_success_result(
        self,
        results: List[SearchResult],
        processing_time: float = 0.0,
        generated_answer: Optional[str] = None
    ) -> HandlerResult:
        """Create a success result"""
        self.logger.info(f"✅ {self.source_type} handler: {len(results)} results in {processing_time:.2f}s")
        return HandlerResult(
            source_type=self.source_type,
            results=results,
            success=True,
            generated_answer=generated_answer,
            processing_time=processing_time
        )

    def _apply_tone_to_prompt(self, base_prompt: str) -> str:
        """
        Apply tone modification to system prompt based on query options

        Args:
            base_prompt: Original system prompt

        Returns:
            Modified prompt with tone instructions
        """
        if not base_prompt:
            return base_prompt

        # Tone modifiers for different communication styles
        tone_modifiers = {
            "resmi": "\n\nDİL TONU: Resmi ve profesyonel bir dil kullan. Saygılı ve kurumsal bir üslup benimse.",
            "samimi": "\n\nDİL TONU: Samimi ve sıcak bir dil kullan. Doğal ve arkadaşça bir üslup benimse.",
            "teknik": "\n\nDİL TONU: Teknik terimler kullan. Detaylı ve hassas açıklamalar yap. Uzmanlara hitap eder gibi yaz.",
            "basit": "\n\nDİL TONU: Basit ve herkesin anlayabileceği bir dil kullan. Teknik terimleri açıkla, sade ifadeler tercih et."
        }

        # Get modifier for current tone (default to resmi if not found)
        modifier = tone_modifiers.get(self.options.tone, "")

        return base_prompt + modifier

    async def _generate_answer(
        self,
        question: str,
        search_results: List[SearchResult],
        max_sources: int = 5
    ) -> Optional[str]:
        """
        Generate answer using scope-specific prompt and retrieved chunks

        Args:
            question: User's question
            search_results: Retrieved search results with chunks
            max_sources: Maximum number of sources to include in context

        Returns:
            Generated answer or None if no prompt configured
        """
        if not self.system_prompt:
            self.logger.warning(f"No system prompt configured for {self.source_type}, skipping answer generation")
            return None

        if not search_results:
            self.logger.warning(f"No search results for {self.source_type}, cannot generate answer")
            return None

        try:
            # Prepare context from search results
            context_parts = []
            for i, result in enumerate(search_results[:max_sources]):
                page_info = f"Sayfa {result.page_number}" if result.page_number else ""

                # Include citations based on options
                if self.options.citations:
                    context_parts.append(
                        f"[Kaynak {i+1} {page_info}]: {result.text}"
                    )
                else:
                    # No citation markers, just the text
                    context_parts.append(result.text)

            context = "\n\n".join(context_parts)

            # Apply tone modification to system prompt
            final_prompt = self._apply_tone_to_prompt(self.system_prompt)

            # Generate answer with OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.logger.info(f"🤖 Generating answer for {self.source_type} with {len(search_results)} sources (tone={self.options.tone}, citations={self.options.citations})...")

            chat_response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": final_prompt
                    },
                    {
                        "role": "user",
                        "content": f"""Kaynak Belgeler:
{context}

Soru: {question}

Lütfen bu soruya kaynak belgelere dayanarak cevap ver ve hangi kaynak(lardan) bilgi aldığını belirt."""
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )

            answer = chat_response.choices[0].message.content
            tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0

            self.logger.info(f"✅ Generated answer for {self.source_type} ({tokens_used} tokens)")
            return answer

        except Exception as e:
            self.logger.error(f"❌ Failed to generate answer for {self.source_type}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
