"""Search handlers for different data sources"""

from app.core.orchestrator.handlers.base import BaseHandler, HandlerResult, SearchResult
from app.core.orchestrator.handlers.collection_handler import CollectionServiceHandler
from app.core.orchestrator.handlers.external_handler import ExternalServiceHandler

__all__ = [
    "BaseHandler",
    "HandlerResult",
    "SearchResult",
    "CollectionServiceHandler",
    "ExternalServiceHandler",
]
