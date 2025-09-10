#!/usr/bin/env python3
"""Clean up old files from raw-documents bucket"""

from minio import Minio
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to MinIO
minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)

def cleanup_raw_documents():
    """Remove old format files from raw-documents bucket"""
    
    bucket = "raw-documents"
    
    # List all objects
    objects = minio_client.list_objects(bucket, recursive=True)
    
    count = 0
    for obj in objects:
        # Remove old format files (original.pdf and metadata.json)
        if obj.object_name.endswith("/original.pdf") or obj.object_name.endswith("/metadata.json"):
            try:
                minio_client.remove_object(bucket, obj.object_name)
                logger.info(f"Deleted old format file: {obj.object_name}")
                count += 1
            except Exception as e:
                logger.error(f"Error deleting {obj.object_name}: {e}")
    
    logger.info(f"Cleaned up {count} old format files from raw-documents")
    return count

if __name__ == "__main__":
    print("Cleaning up old format files from raw-documents bucket...")
    count = cleanup_raw_documents()
    print(f"Cleanup complete! Removed {count} files.")
    print("\nNew files will use the format:")
    print("  - doc_xxx/{original_filename}.pdf")
    print("  - doc_xxx/doc_xxx_metadata.json")