"""
MinIO client management
"""
import logging
import urllib3
from typing import Optional
from minio import Minio
from minio.error import S3Error
from app.config import settings

logger = logging.getLogger(__name__)


class MinIOClientManager:
    """Manages MinIO client connections and bucket operations"""

    def __init__(self):
        """Initialize MinIO client with optimized settings"""
        self._client: Optional[Minio] = None
        self._initialize_client()
        self._ensure_buckets()

    def _initialize_client(self):
        """Initialize MinIO client with custom HTTP settings"""
        try:
            # Create HTTP client with optimized settings
            http_client = urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=60.0, read=600.0),
                maxsize=100,
                retries=urllib3.Retry(
                    total=3,
                    backoff_factor=1.0,
                    status_forcelist=[502, 503, 504]
                )
            )

            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
                http_client=http_client
            )

            logger.info(f"MinIO client initialized for endpoint: {settings.MINIO_ENDPOINT}")

        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    def _ensure_buckets(self):
        """Create required buckets if they don't exist"""
        buckets = [settings.MINIO_BUCKET_DOCS, settings.MINIO_BUCKET_CHUNKS]

        for bucket in buckets:
            try:
                if not self._client.bucket_exists(bucket):
                    self._client.make_bucket(bucket)
                    logger.info(f"Created bucket: {bucket}")
                else:
                    logger.debug(f"Bucket already exists: {bucket}")
            except S3Error as e:
                logger.error(f"Error creating bucket {bucket}: {e}")
                raise

    def get_client(self) -> Minio:
        """
        Get MinIO client instance

        Returns:
            MinIO client
        """
        if not self._client:
            self._initialize_client()
        return self._client

    def create_fresh_client(self) -> Minio:
        """
        Create a fresh MinIO client with new connection pool
        Useful for operations that might encounter connection issues

        Returns:
            New MinIO client instance
        """
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=30.0, read=60.0),
            maxsize=10,
            retries=urllib3.Retry(total=0)
        )

        fresh_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            http_client=http_client
        )

        logger.debug("Created fresh MinIO client instance")
        return fresh_client

    def check_connection(self) -> bool:
        """
        Check if MinIO connection is healthy

        Returns:
            True if connected, False otherwise
        """
        try:
            # Try to list buckets as a health check
            self._client.list_buckets()
            return True
        except Exception as e:
            logger.error(f"MinIO connection check failed: {e}")
            return False