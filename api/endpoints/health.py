"""
Health check endpoint with proper HTTP status codes
"""
import datetime
import logging
import time
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from schemas.api.responses.health import HealthResponse, ServiceStatus, MilvusStatus, MinioStatus, GlobalDBStatus
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import get_embedding_dimension
from app.config import settings
from app.core.storage import storage
from app.services.global_db_service import get_global_db_client

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
    Non-critical services: Global DB (external service, informational only)

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

    # Check Global DB health (non-critical - doesn't affect overall status)
    try:
        global_db_client = get_global_db_client()
        is_healthy = await global_db_client.check_health()

        if is_healthy:
            global_db_status = GlobalDBStatus(
                status="connected",
                message="Connected to Global DB service",
                url=settings.GLOBAL_DB_SERVICE_URL
            )
        else:
            global_db_status = GlobalDBStatus(
                status="disconnected",
                message="Global DB service is unavailable",
                url=settings.GLOBAL_DB_SERVICE_URL
            )
    except Exception as e:
        logger.warning(f"Global DB health check failed: {str(e)}")
        global_db_status = GlobalDBStatus(
            status="disconnected",
            message=f"Cannot connect to Global DB: {str(e)}",
            url=settings.GLOBAL_DB_SERVICE_URL
        )

    # Determine overall status and HTTP status code
    # Only Milvus and MinIO are critical - Global DB is informational
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
            global_db=global_db_status,
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