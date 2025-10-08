"""Base handler interface for search operations"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

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

    def __init__(self, source_type: SourceType):
        self.source_type = source_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

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
