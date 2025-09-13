#!/usr/bin/env python3
"""Simple Milvus collection creation"""

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

# List collections
print("Current collections:", utility.list_collections())

# Create simple schema
id_field = FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=200)
text_field = FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535)
embedding_field = FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
metadata_field = FieldSchema(name="metadata", dtype=DataType.JSON)
doc_id_field = FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=200)
chunk_index_field = FieldSchema(name="chunk_index", dtype=DataType.INT64)
file_name_field = FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=500)
file_type_field = FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=50)
page_num_field = FieldSchema(name="page_num", dtype=DataType.INT64)
chunk_size_field = FieldSchema(name="chunk_size", dtype=DataType.INT64)
created_at_field = FieldSchema(name="created_at", dtype=DataType.INT64)

schema = CollectionSchema(
    fields=[id_field, text_field, embedding_field, metadata_field, doc_id_field,
            chunk_index_field, file_name_field, file_type_field, page_num_field,
            chunk_size_field, created_at_field],
    description=f"RAG collection with {dimension}D embeddings"
)

print(f"Creating collection '{collection_name}'...")

try:
    # Try to create collection
    collection = Collection(name=collection_name, schema=schema)
    print(f"✅ Collection '{collection_name}' created successfully")

    # Create index
    print("Creating index...")
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

except Exception as e:
    print(f"Error: {e}")
    print("Trying alternative approach...")

    # Alternative: use utility.create_collection
    from pymilvus import utility

    # First check and drop if exists
    if collection_name in utility.list_collections():
        utility.drop_collection(collection_name)
        print(f"Dropped existing collection '{collection_name}'")

    # Create using connections directly
    conn = connections.get_connection("default")
    conn.create_collection(collection_name, schema)

    print(f"✅ Collection '{collection_name}' created via direct connection")

    # Get collection and create index
    collection = Collection(collection_name)
    collection.create_index(
        field_name="embedding",
        index_params={
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
    )
    collection.load()
    print("✅ Index created and collection loaded")

# Final verification
print("\nFinal verification:")
print("Collections:", utility.list_collections())
print(f"Collection '{collection_name}' exists:", collection_name in utility.list_collections())