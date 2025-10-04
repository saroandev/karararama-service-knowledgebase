#!/usr/bin/env python3
"""
Main entry point for the RAG API
"""
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

# Import custom JSON response
from api.utils.json_response import CustomJSONResponse

# Import routers
from api.endpoints import health, query, documents, ingest

# Import exception handlers
from app.core.exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    AuthServiceError,
    QuotaExceededError,
    authentication_error_handler,
    insufficient_credits_error_handler,
    auth_service_error_handler,
    quota_exceeded_error_handler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting RAG API server...")
    logger.info("All endpoints are ready at http://0.0.0.0:8080")
    logger.info("API documentation available at http://0.0.0.0:8080/docs")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down RAG API server...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Production RAG API",
    description="Production-ready RAG system with persistent storage",
    version="2.0.0",
    default_response_class=CustomJSONResponse,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Register exception handlers
app.add_exception_handler(AuthenticationError, authentication_error_handler)
app.add_exception_handler(InsufficientCreditsError, insufficient_credits_error_handler)
app.add_exception_handler(AuthServiceError, auth_service_error_handler)
app.add_exception_handler(QuotaExceededError, quota_exceeded_error_handler)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(query.router, tags=["Query"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(ingest.router, tags=["Ingest"])


# Run the app with Uvicorn
if __name__ == "__main__":
    import os

    # Check if running in development mode (default)
    dev_mode = os.getenv("ENV", "development") != "production"

    if dev_mode:
        # Development mode - reload disabled to prevent watchfiles spam
        # If you need auto-reload, set ENV=development_with_reload
        if os.getenv("ENV") == "development_with_reload":
            uvicorn.run(
                "api.main:app",
                host="0.0.0.0",
                port=8080,
                reload=True,
                reload_dirs=["api", "app", "schemas"],  # Only watch specific directories
                reload_includes=["*.py"],  # Only watch Python files
                log_level="info"
            )
        else:
            # Default development mode without reload
            uvicorn.run(
                "api.main:app",
                host="0.0.0.0",
                port=8080,
                reload=False,
                log_level="info"
            )
    else:
        # Production mode without reload
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8080,
            reload=False,
            workers=4,
            log_level="info"
        )