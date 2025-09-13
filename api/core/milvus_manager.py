"""
Milvus connection management
"""
import logging
from pymilvus import connections, Collection
from app.config import settings

logger = logging.getLogger(__name__)


class MilvusConnectionManager:
    """Singleton pattern for Milvus connection management"""
    _instance = None
    _connection = None
    _collection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_connection(self):
        if not connections.has_connection('default'):
            connections.connect(
                'default',
                host=settings.MILVUS_HOST,
                port=str(settings.MILVUS_PORT)
            )
            logger.info(f"Connected to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        return connections

    def get_collection(self):
        if self._collection is None:
            self.get_connection()
            self._collection = Collection(settings.MILVUS_COLLECTION)
            # Ensure collection is loaded
            self._collection.load()
            logger.info(f"Loaded collection: {settings.MILVUS_COLLECTION}")
        return self._collection


# Singleton instance
milvus_manager = MilvusConnectionManager()