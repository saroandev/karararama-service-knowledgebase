"""
Health check endpoint with proper HTTP status codes
"""
import datetime
import logging
import time
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from schemas.api.responses.health import HealthResponse, ServiceStatus, MilvusStatus, MinioStatus
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import get_embedding_dimension
from app.config import settings
from app.core.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint with proper HTTP status codes

    Returns:
    - 200 OK: All critical services are healthy
    - 503 Service Unavailable: One or more critical services are down

    Critical services: Milvus (vector DB), MinIO (object storage)

    Note: Global DB health check has been removed.
    Global DB is now accessed through the orchestrator service.

    Response includes:
    - Overall status: healthy, degraded, or unhealthy
    - Individual service statuses with details
    - Health check latency in milliseconds
    - API version and configuration
    """
    start_time = time.time()

    # Check Milvus health
    milvus_health = milvus_manager.check_health()
    milvus_status = MilvusStatus(
        status=milvus_health["status"],
        message=milvus_health["message"],
        server_version=milvus_health.get("server_version"),
        collections_count=milvus_health.get("collections_count", 0)
    )

    # Check MinIO health (general connection test)
    try:
        # Test connection by listing buckets (works for multi-tenant org-based structure)
        buckets = storage.client_manager.get_client().list_buckets()
        bucket_count = len(buckets)
        minio_status = MinioStatus(
            status="connected",
            message=f"Connected to MinIO (multi-tenant mode, {bucket_count} organization bucket(s) found)"
        )
    except Exception as e:
        logger.warning(f"MinIO health check failed: {str(e)}")
        minio_status = MinioStatus(
            status="disconnected",
            message=f"Cannot connect to MinIO: {str(e)}"
        )

    # Determine overall status and HTTP status code
    if milvus_status.status == "connected" and minio_status.status == "connected":
        overall_status = "healthy"
        http_status_code = status.HTTP_200_OK  # 200
    elif milvus_status.status == "disconnected" and minio_status.status == "disconnected":
        overall_status = "unhealthy"
        http_status_code = status.HTTP_503_SERVICE_UNAVAILABLE  # 503
    else:
        overall_status = "degraded"
        http_status_code = status.HTTP_503_SERVICE_UNAVAILABLE  # 503

    # Calculate health check latency
    latency_ms = int((time.time() - start_time) * 1000)

    # Build response
    response_data = HealthResponse(
        status=overall_status,
        timestamp=datetime.datetime.now().isoformat(),
        services=ServiceStatus(
            milvus=milvus_status,
            minio=minio_status,
            global_db=None,  # Deprecated - moved to orchestrator service
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=get_embedding_dimension()
        ),
        version="1.0.0"
    )

    # Log health check result
    logger.info(f"Health check: {overall_status} (Milvus: {milvus_status.status}, MinIO: {minio_status.status}, latency: {latency_ms}ms)")

    # Return with proper HTTP status code
    return JSONResponse(
        status_code=http_status_code,
        content={
            **response_data.model_dump(),
            "latency_ms": latency_ms  # Add latency to response
        }
    )