#!/usr/bin/env python3
"""Clean up duplicate chunks in MinIO"""

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

def cleanup_chunks():
    """Remove all chunks from MinIO rag-chunks bucket"""
    
    # List all objects in chunks bucket
    objects = minio_client.list_objects(
        settings.MINIO_BUCKET_CHUNKS,
        recursive=True
    )
    
    count = 0
    for obj in objects:
        try:
            minio_client.remove_object(
                settings.MINIO_BUCKET_CHUNKS,
                obj.object_name
            )
            logger.info(f"Deleted: {obj.object_name}")
            count += 1
        except Exception as e:
            logger.error(f"Error deleting {obj.object_name}: {e}")
    
    logger.info(f"Cleaned up {count} chunk files from MinIO")
    return count

if __name__ == "__main__":
    print("Cleaning up duplicate chunks in MinIO...")
    count = cleanup_chunks()
    print(f"Cleanup complete! Removed {count} files.")
    print("\nNow you can re-upload documents to create clean chunk files.")