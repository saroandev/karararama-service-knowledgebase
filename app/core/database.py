"""
Database connection manager for PostgreSQL
"""
import logging
from typing import Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    PostgreSQL database connection manager with connection pooling

    Singleton pattern for efficient connection reuse across the application.
    """
    _instance: Optional['DatabaseManager'] = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize database engine and session factory"""
        if self._engine is None:
            self._initialize_engine()

    def _initialize_engine(self):
        """Create SQLAlchemy engine with connection pooling"""
        database_url = (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )

        logger.info(f"🔌 Connecting to PostgreSQL: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

        # Create engine with connection pooling
        self._engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,  # Number of connections to keep open
            max_overflow=20,  # Additional connections if pool is full
            pool_timeout=30,  # Timeout for getting connection from pool
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL query logging
        )

        # Create session factory
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False
        )

        # Test connection - but don't fail startup if PostgreSQL is not ready yet
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✅ PostgreSQL connection successful")
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL connection failed (will retry on first use): {str(e)}")
            # Don't raise - allow app to start even if PostgreSQL is not ready yet

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions

        Usage:
            with db_manager.get_session() as session:
                session.execute(...)
                session.commit()

        Yields:
            SQLAlchemy Session object
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            session.close()

    def execute_query(self, query: str, params: dict = None):
        """
        Execute a raw SQL query

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Query result
        """
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            return result

    def health_check(self) -> bool:
        """
        Check database connection health

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False

    def close(self):
        """Close all database connections"""
        if self._engine:
            self._engine.dispose()
            logger.info("🔌 Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()
