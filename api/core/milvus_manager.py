"""
Milvus connection management
"""
import logging
from pymilvus import connections, Collection, MilvusException
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
        """Establish connection to Milvus with timeout and retry settings"""
        if not connections.has_connection('default'):
            try:
                connections.connect(
                    'default',
                    host=settings.MILVUS_HOST,
                    port=str(settings.MILVUS_PORT),
                    timeout=settings.MILVUS_CONNECTION_TIMEOUT,
                    retry_on_rpc_failure=settings.MILVUS_MAX_RETRY > 0,
                    max_retry_on_rpc_failure=settings.MILVUS_MAX_RETRY
                )
                logger.info(f"Connected to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
            except Exception as e:
                logger.error(f"Failed to connect to Milvus: {str(e)}")
                raise
        return connections

    def get_collection(self):
        """Get Milvus collection with error handling"""
        if self._collection is None:
            try:
                self.get_connection()
                self._collection = Collection(settings.MILVUS_COLLECTION)
                # Ensure collection is loaded
                self._collection.load()
                logger.info(f"Loaded collection: {settings.MILVUS_COLLECTION}")
            except Exception as e:
                logger.error(f"Failed to get collection: {str(e)}")
                raise
        return self._collection

    def check_health(self) -> dict:
        """Check Milvus connection health without extensive retries

        Returns:
            dict: Health status with keys 'status', 'message', 'entity_count' (if connected)
        """
        try:
            # Try to get connection with minimal retry
            self.get_connection()

            # Try to get collection
            collection = self.get_collection()

            # If we got here, connection is good
            entity_count = collection.num_entities

            return {
                "status": "connected",
                "message": f"Connected to collection '{settings.MILVUS_COLLECTION}'",
                "entity_count": entity_count
            }
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Milvus health check failed: {error_msg}")

            return {
                "status": "disconnected",
                "message": f"Cannot connect to Milvus: {error_msg}",
                "entity_count": None
            }


# Singleton instance
milvus_manager = MilvusConnectionManager()