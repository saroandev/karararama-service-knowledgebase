#!/usr/bin/env python3
"""
Migration script to update Milvus collection schema for MinIO-centric architecture
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pymilvus import connections, utility, Collection
from app.config import settings
from app.index import MilvusIndexer


def migrate_collection():
    """Migrate Milvus collection to new schema"""
    print("=== Milvus Collection Migration ===")
    
    # Connect to Milvus
    connections.connect(
        alias="default",
        host=settings.MILVUS_HOST,
        port=settings.MILVUS_PORT
    )
    print(f"✓ Connected to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    
    collection_name = settings.MILVUS_COLLECTION
    
    # Check if collection exists
    if utility.has_collection(collection_name):
        print(f"⚠ Collection '{collection_name}' exists")
        
        # Get collection info
        collection = Collection(collection_name)
        num_entities = collection.num_entities
        print(f"  Current entities: {num_entities}")
        
        # Ask for confirmation
        response = input(f"Do you want to DROP and recreate '{collection_name}'? (yes/no): ")
        
        if response.lower() == 'yes':
            # Drop existing collection
            collection.drop()
            print(f"✓ Dropped collection '{collection_name}'")
            
            # Recreate with new schema
            indexer = MilvusIndexer()
            print(f"✓ Created new collection with MinIO-centric schema")
            
            # Verify new schema
            collection = Collection(collection_name)
            schema = collection.schema
            field_names = [field.name for field in schema.fields]
            
            print("\nNew schema fields:")
            for field in schema.fields:
                print(f"  - {field.name}: {field.dtype}")
            
            # Check for expected fields
            if "minio_object_path" in field_names and "text" not in field_names:
                print("\n✅ Migration successful!")
                print("  - 'text' field removed")
                print("  - 'minio_object_path' field added")
            else:
                print("\n⚠ Schema may not be correct. Please verify.")
        else:
            print("Migration cancelled.")
    else:
        print(f"Collection '{collection_name}' does not exist. Creating new one...")
        indexer = MilvusIndexer()
        print(f"✓ Created new collection with MinIO-centric schema")


if __name__ == "__main__":
    try:
        migrate_collection()
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)