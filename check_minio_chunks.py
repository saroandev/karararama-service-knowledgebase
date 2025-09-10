#!/usr/bin/env python3
"""Check MinIO chunk structure and compare with Milvus"""

from minio import Minio
from pymilvus import connections, Collection
from app.config import settings
import json

# Connect to MinIO
minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)

# Connect to Milvus
connections.connect(
    alias="default",
    host=settings.MILVUS_HOST,
    port=settings.MILVUS_PORT
)

# Get Milvus collection
collection = Collection(settings.MILVUS_COLLECTION)
collection.load()

# Get a sample document from Milvus
results = collection.query(
    expr="document_id != ''",
    limit=1,
    output_fields=["document_id", "id", "text"]
)

if results:
    doc_id = results[0]["document_id"]
    print(f"Checking document: {doc_id}")
    
    # Get all chunks for this document from Milvus
    milvus_chunks = collection.query(
        expr=f'document_id == "{doc_id}"',
        output_fields=["id", "document_id", "chunk_index", "text"]
    )
    
    print(f"\nMilvus chunks for {doc_id}:")
    for chunk in milvus_chunks:
        print(f"  - Chunk ID: {chunk['id']}")
    
    # Check MinIO structure
    print(f"\nMinIO chunks in rag-chunks bucket:")
    objects = minio_client.list_objects(
        settings.MINIO_BUCKET_CHUNKS,
        prefix=f"{doc_id}/",
        recursive=True
    )
    
    minio_files = []
    for obj in objects:
        minio_files.append(obj.object_name)
        print(f"  - {obj.object_name}")
    
    print(f"\nSummary:")
    print(f"  Milvus chunks: {len(milvus_chunks)}")
    print(f"  MinIO files: {len(minio_files)}")
    
    # Check naming pattern
    if minio_files:
        print(f"\nMinIO file naming pattern:")
        for f in minio_files[:3]:
            print(f"  - {f}")
else:
    print("No documents found in Milvus")