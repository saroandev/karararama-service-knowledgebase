import logging
from typing import List, Dict, Any, Optional
import json
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

from app.config import settings

logger = logging.getLogger(__name__)


class MilvusIndexer:
    def __init__(self):
        self.host = settings.MILVUS_HOST
        self.port = settings.MILVUS_PORT
        self.collection_name = settings.MILVUS_COLLECTION
        self.collection = None
        self._connect()
        self._ensure_collection()
    
    def _connect(self):
        """Connect to Milvus server"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        if utility.has_collection(self.collection_name):
            logger.info(f"Collection {self.collection_name} already exists")
            self.collection = Collection(self.collection_name)
        else:
            logger.info(f"Creating collection {self.collection_name}")
            self._create_collection()
    
    def _create_collection(self):
        """Create Milvus collection with schema"""
        # Define schema  
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),  # multilingual-e5-small uses 384 dim
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="page_number", dtype=DataType.INT64),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="created_at", dtype=DataType.INT64)
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description="RAG document chunks collection"
        )
        
        # Create collection
        self.collection = Collection(
            name=self.collection_name,
            schema=schema
        )
        
        # Create index for vector field
        index_params = {
            "metric_type": "IP",  # Inner Product for normalized vectors
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        
        self.collection.create_index(
            field_name="embedding",
            index_params=index_params
        )
        
        logger.info(f"Created collection {self.collection_name} with index")
    
    def insert_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[np.ndarray]) -> int:
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
            "text": [],
            "metadata": [],
            "created_at": []
        }
        
        timestamp = int(datetime.now().timestamp())
        
        for chunk, embedding in zip(chunks, embeddings):
            # Ensure embedding is correct dimension
            expected_dim = 384  # multilingual-e5-small dimension
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
            data["text"].append(chunk.get("text", "")[:65535])  # Truncate if too long
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
        filters: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional filter expression
        
        Returns:
            List of search results with scores
        """
        # Ensure collection is loaded
        if not self.collection.is_loaded:
            self.collection.load()
        
        # Prepare search parameters
        search_params = {
            "metric_type": "IP",
            "params": {"nprobe": 16}
        }
        
        # Execute search
        results = self.collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filters,
            output_fields=["document_id", "chunk_id", "chunk_index", "page_number", "text", "metadata"]
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
                    "text": hit.entity.get("text"),
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
            "schema": str(self.collection.schema)
        }
        
        return stats
    
    def create_partition(self, partition_name: str):
        """Create a partition in the collection"""
        if not self.collection.has_partition(partition_name):
            self.collection.create_partition(partition_name)
            logger.info(f"Created partition: {partition_name}")
        else:
            logger.info(f"Partition already exists: {partition_name}")
    
    def drop_collection(self):
        """Drop the entire collection"""
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            logger.info(f"Dropped collection: {self.collection_name}")
            self.collection = None
    
    def rebuild_index(self):
        """Rebuild the vector index"""
        if not self.collection:
            return
        
        # Drop existing index
        self.collection.drop_index()
        
        # Create new index
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        
        self.collection.create_index(
            field_name="embedding",
            index_params=index_params
        )
        
        logger.info("Rebuilt vector index")
    
    def batch_search(
        self,
        query_embeddings: List[np.ndarray],
        top_k: int = 10,
        filters: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Batch search for multiple queries
        
        Args:
            query_embeddings: List of query embedding vectors
            top_k: Number of results per query
            filters: Optional filter expression
        
        Returns:
            List of search results for each query
        """
        # Ensure collection is loaded
        if not self.collection.is_loaded:
            self.collection.load()
        
        # Prepare search parameters
        search_params = {
            "metric_type": "IP",
            "params": {"nprobe": 16}
        }
        
        # Convert embeddings to list format
        query_data = [emb.tolist() for emb in query_embeddings]
        
        # Execute batch search
        results = self.collection.search(
            data=query_data,
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filters,
            output_fields=["document_id", "chunk_id", "chunk_index", "page_number", "text", "metadata"]
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
                    "text": hit.entity.get("text"),
                    "metadata": json.loads(hit.entity.get("metadata", "{}"))
                }
                query_hits.append(result)
            all_results.append(query_hits)
        
        return all_results


# Singleton instance
milvus_indexer = MilvusIndexer()