#!/usr/bin/env python3
"""Verify chunk consistency between Milvus and MinIO"""

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

# Check the new document
doc_id = "doc_06054c7f7733730e"
print(f"Checking document: {doc_id}")

# Get all chunks for this document from Milvus
milvus_chunks = collection.query(
    expr=f'document_id == "{doc_id}"',
    output_fields=["id", "document_id", "chunk_index", "text"]
)

print(f"\n✅ Milvus chunks for {doc_id}:")
milvus_chunk_ids = []
for chunk in milvus_chunks:
    print(f"  - Chunk ID: {chunk['id']}")
    milvus_chunk_ids.append(chunk['id'])

# Check MinIO structure
print(f"\n✅ MinIO chunks in rag-chunks bucket:")
objects = list(minio_client.list_objects(
    settings.MINIO_BUCKET_CHUNKS,
    prefix=f"{doc_id}/",
    recursive=True
))

minio_files = []
for obj in objects:
    minio_files.append(obj.object_name)
    # Extract chunk_id from file path
    # Format: doc_xxx/doc_xxx_0000.json
    file_name = obj.object_name.split('/')[-1].replace('.json', '')
    print(f"  - {obj.object_name} (chunk_id: {file_name})")

print(f"\n📊 Summary:")
print(f"  Milvus chunks: {len(milvus_chunks)}")
print(f"  MinIO files: {len(minio_files)}")

# Check if they match
if len(milvus_chunks) == len(minio_files):
    print(f"\n✅ SUCCESS: Chunk counts match! No duplicates.")
    
    # Verify chunk_id naming
    print(f"\n🔍 Verifying chunk_id consistency:")
    for milvus_id in milvus_chunk_ids:
        expected_minio_path = f"{doc_id}/{milvus_id}.json"
        if expected_minio_path in minio_files:
            print(f"  ✅ {milvus_id} -> {expected_minio_path}")
        else:
            print(f"  ❌ {milvus_id} -> NOT FOUND in MinIO")
else:
    print(f"\n❌ ERROR: Chunk count mismatch!")
    print(f"  Expected {len(milvus_chunks)} files in MinIO, but found {len(minio_files)}")
    
    # Show duplicates if any
    if len(minio_files) > len(milvus_chunks):
        print(f"\n  Duplicate files in MinIO:")
        for f in minio_files:
            print(f"    - {f}")