"""
Health check endpoint
"""
import datetime
import logging
from fastapi import APIRouter
from schemas.api.responses.health import HealthResponse, ServiceStatus, MilvusStatus, MinioStatus
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import get_embedding_dimension
from app.config import settings
from app.core.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint

    Returns health status of the system and its dependencies.
    Returns 200 even if some services are down to allow API to report its status.
    """
    # Check Milvus health
    milvus_health = milvus_manager.check_health()
    milvus_status = MilvusStatus(
        status=milvus_health["status"],
        message=milvus_health["message"],
        collection=settings.MILVUS_COLLECTION if milvus_health["status"] == "connected" else None,
        entities=milvus_health.get("entity_count")
    )

    # Check MinIO health
    try:
        bucket_exists = storage.client.bucket_exists(settings.MINIO_BUCKET_DOCS)
        minio_status = MinioStatus(
            status="connected",
            message=f"Connected to bucket '{settings.MINIO_BUCKET_DOCS}'"
        )
    except Exception as e:
        logger.warning(f"MinIO health check failed: {str(e)}")
        minio_status = MinioStatus(
            status="disconnected",
            message=f"Cannot connect to MinIO: {str(e)}"
        )

    # Determine overall status
    if milvus_status.status == "connected" and minio_status.status == "connected":
        overall_status = "healthy"
    elif milvus_status.status == "disconnected" and minio_status.status == "disconnected":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.datetime.now().isoformat(),
        services=ServiceStatus(
            milvus=milvus_status,
            minio=minio_status,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=get_embedding_dimension()
        ),
        version="2.0.0"
    )