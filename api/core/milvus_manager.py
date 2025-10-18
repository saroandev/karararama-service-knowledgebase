"""
Milvus connection management with multi-tenant scope support
"""
import logging
from typing import Dict, List, Optional
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from app.config import settings
from schemas.api.requests.scope import ScopeIdentifier, DataScope
from app.core.auth import UserContext

logger = logging.getLogger(__name__)


class MilvusConnectionManager:
    """
    Singleton pattern for Milvus connection management with multi-tenant support

    Manages multiple collections for different organizations and users.
    Each scope (private or shared) has its own collection.
    """
    _instance = None
    _connection = None
    _collections: Dict[str, Collection] = {}  # Cache for loaded collections

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

    def get_collection(self, scope: ScopeIdentifier, auto_create: bool = True) -> Collection:
        """
        Get Milvus collection for the specified scope

        Args:
            scope: ScopeIdentifier for multi-tenant (REQUIRED - no legacy mode)
            auto_create: If True, creates collection if it doesn't exist. If False, raises exception.

        Returns:
            Collection instance

        Raises:
            ValueError: If scope is None
            Exception: If collection doesn't exist and auto_create is False
        """
        if scope is None:
            raise ValueError(
                "Collection scope is required. Legacy MILVUS_COLLECTION mode has been removed. "
                "Please provide a ScopeIdentifier with organization_id, scope_type, and optional collection_name."
            )

        collection_name = scope.get_collection_name(dimension=settings.EMBEDDING_DIMENSION)

        # Check cache
        if collection_name in self._collections:
            return self._collections[collection_name]

        try:
            self.get_connection()

            # Check if collection exists
            if not utility.has_collection(collection_name):
                if auto_create:
                    logger.warning(f"Collection {collection_name} does not exist, creating...")
                    self._create_collection(collection_name)
                else:
                    # Collection doesn't exist and auto-create is disabled
                    raise Exception(f"Collection '{collection_name}' does not exist")

            # Get collection instance
            collection = Collection(collection_name)
            # NOTE: Lazy loading - collection.load() removed to avoid MinIO deadlock
            # Milvus will auto-load the collection on first search operation
            # collection.load()  # ❌ Causes blocking/deadlock with multiple collections

            # Cache it
            self._collections[collection_name] = collection
            logger.info(f"Retrieved collection (lazy load): {collection_name}")

            return collection

        except Exception as e:
            logger.error(f"Failed to get collection {collection_name}: {str(e)}")
            raise

    def _create_collection(self, collection_name: str):
        """
        Create a new collection with standard schema

        All collections use the same schema for consistency:
        - id (VARCHAR, primary key)
        - document_id (VARCHAR)
        - chunk_index (INT64)
        - text (VARCHAR)
        - embedding (FLOAT_VECTOR)
        - metadata (JSON)
        """
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIMENSION),
            FieldSchema(name="metadata", dtype=DataType.JSON)
        ]

        schema = CollectionSchema(
            fields=fields,
            description=f"Multi-tenant RAG collection: {collection_name}"
        )

        collection = Collection(name=collection_name, schema=schema)

        # Create HNSW index on embedding field
        index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 256}
        }
        collection.create_index(field_name="embedding", index_params=index_params)

        logger.info(f"Created collection: {collection_name} with HNSW index")

    def get_user_accessible_collections(self, user_context: UserContext) -> List[Collection]:
        """
        Get all collections accessible by the user based on their data_access scope

        Args:
            user_context: User context with organization and access scope

        Returns:
            List of Collection objects the user can access
        """
        collections = []

        # User's private data
        if user_context.data_access.own_data:
            private_scope = ScopeIdentifier(
                organization_id=user_context.organization_id,
                scope_type=DataScope.PRIVATE,
                user_id=user_context.user_id
            )
            try:
                collections.append(self.get_collection(private_scope))
                logger.info(f"Added private collection for user {user_context.user_id}")
            except Exception as e:
                logger.warning(f"Could not load private collection: {e}")

        # Organization shared data
        if user_context.data_access.shared_data:
            shared_scope = ScopeIdentifier(
                organization_id=user_context.organization_id,
                scope_type=DataScope.SHARED
            )
            try:
                collections.append(self.get_collection(shared_scope))
                logger.info(f"Added shared collection for org {user_context.organization_id}")
            except Exception as e:
                logger.warning(f"Could not load shared collection: {e}")

        return collections

    def list_all_collections(self) -> List[str]:
        """
        List all collections in Milvus

        Returns:
            List of collection names
        """
        try:
            self.get_connection()
            return utility.list_collections()
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def check_health(self) -> dict:
        """Check Milvus connection health without checking specific collections

        Returns:
            dict: Health status with keys 'status', 'message', 'server_version', 'collections_count'
        """
        try:
            # Try to get connection with minimal retry
            self.get_connection()

            # Get server version to verify connection
            server_version = utility.get_server_version()

            # List all collections
            all_collections = utility.list_collections()
            collections_count = len(all_collections)

            return {
                "status": "connected",
                "message": f"Connected to Milvus server v{server_version}",
                "server_version": server_version,
                "collections_count": collections_count
            }
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Milvus health check failed: {error_msg}")

            return {
                "status": "disconnected",
                "message": f"Cannot connect to Milvus: {error_msg}",
                "server_version": None,
                "collections_count": 0
            }


# Singleton instance
milvus_manager = MilvusConnectionManager()