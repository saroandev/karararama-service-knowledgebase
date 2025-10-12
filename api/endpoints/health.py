"""
Health check endpoint
"""
import datetime
import logging
from fastapi import APIRouter
from schemas.api.responses.health import HealthResponse, ServiceStatus, MilvusStatus, MinioStatus, GlobalDBStatus
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import get_embedding_dimension
from app.config import settings
from app.core.storage import storage
from app.services.global_db_service import get_global_db_client

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

    # Determine overall status (Global DB is informational only, doesn't affect overall status)
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
            global_db=global_db_status,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=get_embedding_dimension()
        ),
        version="2.0.0"
    )