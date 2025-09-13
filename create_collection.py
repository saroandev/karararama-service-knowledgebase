#!/usr/bin/env python3
"""Create Milvus collection for RAG system"""

from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
import os
from dotenv import load_dotenv

load_dotenv()

def create_rag_collection():
    # Connect to Milvus
    host = os.getenv("MILVUS_HOST", "localhost")
    port = int(os.getenv("MILVUS_PORT", "19530"))
    collection_name = os.getenv("MILVUS_COLLECTION", "rag_chunks_1536")
    dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    print(f"Connecting to Milvus at {host}:{port}")
    connections.connect("default", host=host, port=port)

    # Check if collection exists
    try:
        if utility.has_collection(collection_name):
            print(f"Collection '{collection_name}' already exists")
            collection = Collection(collection_name)
            print(f"Collection info: {collection.num_entities} entities")
            return
    except Exception as e:
        print(f"Collection does not exist, creating new one...")

    # Define schema
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=200),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
        FieldSchema(name="metadata", dtype=DataType.JSON),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="page_num", dtype=DataType.INT64),
        FieldSchema(name="chunk_size", dtype=DataType.INT64),
        FieldSchema(name="created_at", dtype=DataType.INT64)
    ]

    schema = CollectionSchema(
        fields=fields,
        description=f"RAG chunks collection with {dimension}D embeddings"
    )

    print(f"Creating collection '{collection_name}' with {dimension}D embeddings")
    collection = Collection(
        name=collection_name,
        schema=schema,
        using='default'
    )

    # Create index for vector field
    print("Creating IVF_FLAT index on embedding field")
    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024}
    }
    collection.create_index(
        field_name="embedding",
        index_params=index_params
    )

    # Load collection
    print("Loading collection into memory")
    collection.load()

    print(f"✅ Collection '{collection_name}' created successfully")
    print(f"   - Dimension: {dimension}")
    print(f"   - Index: IVF_FLAT with COSINE metric")
    print(f"   - Status: Loaded")

if __name__ == "__main__":
    create_rag_collection()