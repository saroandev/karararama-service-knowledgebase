"""
Base storage interface and abstract classes
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class BaseStorage(ABC):
    """Abstract base class for storage implementations"""

    @abstractmethod
    def upload_document(self, document_id: str, file_data: bytes,
                       filename: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Upload a document to storage"""
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[bytes]:
        """Retrieve a document from storage"""
        pass

    @abstractmethod
    def delete_document(self, document_id: str) -> bool:
        """Delete a document from storage"""
        pass

    @abstractmethod
    def document_exists(self, document_id: str) -> bool:
        """Check if a document exists"""
        pass

    @abstractmethod
    def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents in storage"""
        pass


class BaseChunkStorage(ABC):
    """Abstract base class for chunk storage"""

    @abstractmethod
    def upload_chunk(self, document_id: str, chunk_id: str,
                    chunk_text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Upload a single chunk"""
        pass

    @abstractmethod
    def get_chunks(self, document_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get all chunks for a document"""
        pass

    @abstractmethod
    def delete_chunks(self, document_id: str) -> bool:
        """Delete all chunks for a document"""
        pass


class BaseCacheManager(ABC):
    """Abstract base class for cache management"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        pass

    @abstractmethod
    def invalidate(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache"""
        pass