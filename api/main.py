#!/usr/bin/env python3
"""
Main entry point for the RAG API
"""
import logging
import sys
from pathlib import Path
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Production RAG API",
    description="Production-ready RAG system with persistent storage",
    version="2.0.0",
    default_response_class=CustomJSONResponse
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(query.router, tags=["Query"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(ingest.router, tags=["Ingest"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting RAG API server...")
    logger.info("All endpoints are ready at http://0.0.0.0:8080")
    logger.info("API documentation available at http://0.0.0.0:8080/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down RAG API server...")


# Run the app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )