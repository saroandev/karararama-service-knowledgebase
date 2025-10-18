"""
Milvus vector database indexer implementation

DEPRECATED: This module is deprecated and should not be used.
Use api/core/milvus_manager.py with scope-based collections instead.

The MilvusIndexer class still uses legacy MILVUS_COLLECTION which has been removed.
For new code, use MilvusConnectionManager.get_collection() with ScopeIdentifier.
"""
import logging
import warnings

warnings.warn(
    "MilvusIndexer is deprecated. Use api/core/milvus_manager.py with scope-based collections instead.",
    DeprecationWarning,
    stacklevel=2
)
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)
import numpy as np

from app.core.indexing.base import AbstractIndexer
from app.config import settings

logger = logging.getLogger(__name__)


class MilvusIndexer(AbstractIndexer):
    """Milvus vector database indexer"""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None
    ):
        """
        Initialize Milvus indexer

        Args:
            collection_name: Name of the Milvus collection
            host: Milvus server host
            port: Milvus server port
        """
        collection_name = collection_name or settings.MILVUS_COLLECTION
        super().__init__(collection_name)

        self.host = host or settings.MILVUS_HOST
        self.port = port or settings.MILVUS_PORT
        self.collection = None

        # Connect and ensure collection exists
        self.connect()
        self._ensure_collection()

    def connect(self) -> bool:
        """
        Connect to Milvus server

        Returns:
            True if connection successful, False otherwise
        """
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            return False

    def create_collection(
        self,
        dimension: int = None,
        **kwargs
    ) -> bool:
        """
        Create a new Milvus collection

        Args:
            dimension: Dimension of vectors (uses settings if not provided)
            **kwargs: Additional configuration parameters

        Returns:
            True if creation successful, False otherwise
        """
        try:
            dimension = dimension or settings.EMBEDDING_DIMENSION

            # Define schema
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="page_number", dtype=DataType.INT64),
                FieldSchema(name="minio_object_path", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="created_at", dtype=DataType.INT64)
            ]

            schema = CollectionSchema(
                fields=fields,
                description=kwargs.get("description", "RAG document chunks collection")
            )

            # Create collection
            self.collection = Collection(
                name=self.collection_name,
                schema=schema
            )

            # Create index for vector field
            index_type = kwargs.get("index_type", "IVF_FLAT")
            metric_type = kwargs.get("metric_type", "COSINE")
            nlist = kwargs.get("nlist", 128)

            index_params = {
                "metric_type": metric_type,
                "index_type": index_type,
                "params": {"nlist": nlist}
            }

            self.collection.create_index(
                field_name="embedding",
                index_params=index_params
            )

            logger.info(f"Created collection {self.collection_name} with index")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def insert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[np.ndarray]
    ) -> int:
        """
        Insert chunks with embeddings into Milvus

        Args:
            chunks: List of chunk dictionaries
            embeddings: List of embedding vectors

        Returns:
            Number of inserted items
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")

        if not chunks:
            return 0

        # Prepare data for insertion
        data = {
            "id": [],
            "embedding": [],
            "document_id": [],
            "chunk_id": [],
            "chunk_index": [],
            "page_number": [],
            "minio_object_path": [],
            "metadata": [],
            "created_at": []
        }

        timestamp = int(datetime.now().timestamp())
        expected_dim = settings.EMBEDDING_DIMENSION

        for chunk, embedding in zip(chunks, embeddings):
            # Ensure embedding is correct dimension
            if len(embedding) != expected_dim:
                logger.warning(f"Embedding dimension mismatch: {len(embedding)} != {expected_dim}")
                # Pad or truncate as needed
                if len(embedding) < expected_dim:
                    embedding = np.pad(embedding, (0, expected_dim - len(embedding)))
                else:
                    embedding = embedding[:expected_dim]

            data["id"].append(chunk.get("chunk_id", ""))
            data["embedding"].append(embedding.tolist())
            data["document_id"].append(chunk.get("document_id", ""))
            data["chunk_id"].append(chunk.get("chunk_id", ""))
            data["chunk_index"].append(chunk.get("chunk_index", 0))
            data["page_number"].append(chunk.get("metadata", {}).get("page_number", 0))
            data["minio_object_path"].append(chunk.get("minio_object_path", ""))
            data["metadata"].append(json.dumps(chunk.get("metadata", {}))[:65535])
            data["created_at"].append(timestamp)

        try:
            # Insert data
            insert_result = self.collection.insert(data)

            # Flush to ensure data is persisted
            self.collection.flush()

            inserted_count = len(insert_result.primary_keys)
            logger.info(f"Inserted {inserted_count} chunks into Milvus")

            return inserted_count

        except Exception as e:
            logger.error(f"Error inserting chunks: {e}")
            raise

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters (converted to Milvus expression)

        Returns:
            List of search results with scores
        """
        # Ensure collection is loaded
        if not self.collection.is_loaded:
            self.collection.load()

        # Prepare search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16}
        }

        # Convert filters dict to Milvus expression if provided
        expr = None
        if filters:
            expr = self._build_filter_expression(filters)

        # Execute search
        results = self.collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["document_id", "chunk_id", "chunk_index", "page_number", "minio_object_path", "metadata"]
        )

        # Format results
        search_results = []
        for hits in results:
            for hit in hits:
                result = {
                    "id": hit.id,
                    "score": hit.score,
                    "document_id": hit.entity.get("document_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "page_number": hit.entity.get("page_number"),
                    "minio_object_path": hit.entity.get("minio_object_path"),
                    "metadata": json.loads(hit.entity.get("metadata", "{}"))
                }
                search_results.append(result)

        return search_results

    def delete_by_document(self, document_id: str) -> bool:
        """
        Delete all chunks for a document

        Args:
            document_id: Document identifier

        Returns:
            Success status
        """
        try:
            expr = f'document_id == "{document_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            logger.info(f"Deleted chunks for document: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting chunks: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.collection:
            return {}

        stats = {
            "name": self.collection_name,
            "num_entities": self.collection.num_entities,
            "is_loaded": self.collection.is_loaded,
            "dimension": settings.EMBEDDING_DIMENSION,
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE"
        }

        return stats

    def batch_search(
        self,
        query_embeddings: List[np.ndarray],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Batch search for multiple queries

        Args:
            query_embeddings: List of query embedding vectors
            top_k: Number of results per query
            filters: Optional filters

        Returns:
            List of search results for each query
        """
        # Ensure collection is loaded
        if not self.collection.is_loaded:
            self.collection.load()

        # Prepare search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16}
        }

        # Convert filters dict to expression if provided
        expr = None
        if filters:
            expr = self._build_filter_expression(filters)

        # Convert embeddings to list format
        query_data = [emb.tolist() for emb in query_embeddings]

        # Execute batch search
        results = self.collection.search(
            data=query_data,
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["document_id", "chunk_id", "chunk_index", "page_number", "minio_object_path", "metadata"]
        )

        # Format results for each query
        all_results = []
        for query_results in results:
            query_hits = []
            for hit in query_results:
                result = {
                    "id": hit.id,
                    "score": hit.score,
                    "document_id": hit.entity.get("document_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "page_number": hit.entity.get("page_number"),
                    "minio_object_path": hit.entity.get("minio_object_path"),
                    "metadata": json.loads(hit.entity.get("metadata", "{}"))
                }
                query_hits.append(result)
            all_results.append(query_hits)

        return all_results

    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        if utility.has_collection(self.collection_name):
            logger.info(f"Collection {self.collection_name} already exists")
            self.collection = Collection(self.collection_name)
        else:
            logger.info(f"Creating collection {self.collection_name}")
            self.create_collection()

    def _build_filter_expression(self, filters: Dict[str, Any]) -> str:
        """
        Build Milvus filter expression from dictionary

        Args:
            filters: Dictionary of filters

        Returns:
            Milvus expression string
        """
        expressions = []

        for key, value in filters.items():
            if isinstance(value, str):
                expressions.append(f'{key} == "{value}"')
            elif isinstance(value, (int, float)):
                expressions.append(f'{key} == {value}')
            elif isinstance(value, list):
                # For list values, use IN operator
                values_str = ', '.join([f'"{v}"' if isinstance(v, str) else str(v) for v in value])
                expressions.append(f'{key} in [{values_str}]')

        return ' and '.join(expressions) if expressions else None

    def create_partition(self, partition_name: str) -> bool:
        """Create a partition in the collection"""
        try:
            if not self.collection.has_partition(partition_name):
                self.collection.create_partition(partition_name)
                logger.info(f"Created partition: {partition_name}")
            else:
                logger.info(f"Partition already exists: {partition_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create partition: {e}")
            return False

    def drop_collection(self) -> bool:
        """Drop the entire collection"""
        try:
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                logger.info(f"Dropped collection: {self.collection_name}")
                self.collection = None
            return True
        except Exception as e:
            logger.error(f"Failed to drop collection: {e}")
            return False

    def rebuild_index(self) -> bool:
        """Rebuild the vector index"""
        if not self.collection:
            return False

        try:
            # Drop existing index
            self.collection.drop_index()

            # Create new index
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }

            self.collection.create_index(
                field_name="embedding",
                index_params=index_params
            )

            logger.info("Rebuilt vector index")
            return True

        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            return False