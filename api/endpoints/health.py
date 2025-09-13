"""
Health check endpoint
"""
import datetime
import logging
from fastapi import APIRouter, HTTPException
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import get_embedding_dimension
from app.config import settings
from app.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test connections
        collection = milvus_manager.get_collection()
        entity_count = collection.num_entities

        # Test MinIO
        minio_status = "connected" if storage.client.bucket_exists(settings.MINIO_BUCKET_DOCS) else "error"

        return {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "services": {
                "milvus": "connected",
                "minio": minio_status,
                "collection": settings.MILVUS_COLLECTION,
                "entities": entity_count,
                "embedding_model": settings.EMBEDDING_MODEL,
                "embedding_dimension": get_embedding_dimension()
            },
            "version": "2.0.0"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")