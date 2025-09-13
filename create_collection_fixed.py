#!/usr/bin/env python3
"""Create Milvus collection with correct field names for production server"""

from pymilvus import connections, utility, CollectionSchema, FieldSchema, DataType, Collection
import os
from dotenv import load_dotenv

load_dotenv()

# Connect
host = os.getenv("MILVUS_HOST", "localhost")
port = int(os.getenv("MILVUS_PORT", "19530"))
collection_name = os.getenv("MILVUS_COLLECTION", "rag_chunks_1536")
dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

print(f"Connecting to Milvus at {host}:{port}")
connections.connect("default", host=host, port=port)

# Check and drop if exists
if utility.has_collection(collection_name):
    utility.drop_collection(collection_name)
    print(f"Dropped existing collection '{collection_name}'")

# Create schema matching production_server.py requirements
fields = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=200),
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=200),  # Changed from doc_id
    FieldSchema(name="chunk_index", dtype=DataType.INT64),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
    FieldSchema(name="metadata", dtype=DataType.JSON)
]

schema = CollectionSchema(
    fields=fields,
    description=f"RAG collection with {dimension}D embeddings - production compatible"
)

print(f"Creating collection '{collection_name}' with correct field names...")

# Create collection
collection = Collection(name=collection_name, schema=schema)
print(f"✅ Collection '{collection_name}' created successfully")

# Create index
print("Creating COSINE index...")
collection.create_index(
    field_name="embedding",
    index_params={
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024}
    }
)
print("✅ Index created")

# Load collection
collection.load()
print("✅ Collection loaded")

# Verify fields
print("\n📋 Collection fields:")
for field in collection.schema.fields:
    print(f"  - {field.name}: {field.dtype.name}")

print(f"\n✅ Collection '{collection_name}' is ready for production use")
print(f"  - Has 'document_id' field (compatible with production_server.py)")
print(f"  - Dimension: {dimension}")
print(f"  - Metric: COSINE")