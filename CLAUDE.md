# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OneDocs RAG Pipeline - A Turkish-language Retrieval-Augmented Generation system for PDF document analysis. Built with FastAPI, Milvus vector database, MinIO object storage, and OpenAI GPT models.

## Key Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Running Services

#### Docker Services (Required Infrastructure)
```bash
# Start all infrastructure services (Milvus, MinIO, etcd, Attu)
docker compose up -d

# Check service health
docker compose ps

# View logs
docker compose logs -f [service_name]

# Stop services
docker compose down
```

#### FastAPI Application
```bash
# Development server with auto-reload
uvicorn app.server:app --reload --port 8080

# Production server
python production_server.py
```

#### Streamlit Chat Interface
```bash
# Start chat UI (requires FastAPI running)
./run_streamlit.sh
# Or directly:
streamlit run streamlit_chat_app.py --server.port=8501
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/     # Integration tests only

# Run with parallel execution
pytest -n auto
```

### Code Quality
```bash
# Format code
black app/
isort app/

# Type checking (if mypy configured)
mypy app/
```

## Architecture Overview

### Core Pipeline Flow
1. **PDF Ingestion** (`app/ingest.py`): Orchestrates document upload and processing
2. **Parsing** (`app/parse.py`): Extracts text and metadata from PDFs using PyMuPDF
3. **Chunking** (`app/chunk.py`): Splits documents into semantic chunks with overlap
4. **Embedding** (`app/embed.py`): Generates vector embeddings using OpenAI or local models
5. **Indexing** (`app/index.py`): Stores vectors in Milvus with metadata
6. **Storage** (`app/storage.py`): Manages raw documents and chunks in MinIO
7. **Retrieval** (`app/retrieve.py`): Performs semantic search and reranking
8. **Generation** (`app/generate.py`): Produces answers using LLM with retrieved context

### Key Components

#### Milvus Collections
- **rag_chunks_1536**: Main collection for document chunks with 1536-dim embeddings
- **raw_documents**: Stores document metadata and processing status
- Uses HNSW indexing for efficient similarity search

#### MinIO Buckets
- **raw-documents**: Original PDF files
- **document-chunks**: Processed text chunks with metadata
- Provides S3-compatible object storage

#### API Endpoints (app/server.py)
- `POST /ingest`: Upload and process PDFs
- `POST /query`: Ask questions about documents
- `GET /documents`: List uploaded documents
- `DELETE /documents/{id}`: Remove documents
- `GET /health`: System health check
- WebSocket `/ws/progress`: Real-time ingestion progress

### Configuration (app/config.py)
Environment variables control:
- OpenAI API settings (model, embeddings)
- Milvus connection (host, port, collections)
- MinIO credentials and endpoints
- Processing parameters (chunk size, overlap)

### Processing Strategies
- **Chunking**: Token-based or character-based splitting with configurable overlap
- **Embedding**: OpenAI text-embedding-3-small or local multilingual models
- **Reranking**: Optional cross-encoder for improved relevance

## Important Patterns

### Error Handling
- All services use comprehensive try-catch blocks with detailed logging
- Connection retries implemented for Milvus and MinIO
- Graceful degradation when optional features unavailable

### Async Operations
- FastAPI endpoints use async/await for I/O operations
- Background tasks for long-running ingestion processes
- WebSocket support for real-time progress updates

### Testing Approach
- Unit tests mock external dependencies (Milvus, MinIO, OpenAI)
- Integration tests verify end-to-end pipeline functionality
- Docker service health checks before integration tests

## Service URLs
- **API Documentation**: http://localhost:8080/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)
- **Milvus Attu UI**: http://localhost:8000
- **Streamlit Chat**: http://localhost:8501

## Common Development Tasks

### Adding New Document Types
Extend `app/parse.py` to handle additional formats beyond PDF.

### Modifying Chunk Strategy
Update `app/chunk.py` for custom chunking logic (semantic, sliding window, etc.).

### Changing Embedding Model
Configure in `app/embed.py` - supports OpenAI, HuggingFace, and local models.

### Customizing Retrieval
Adjust search parameters in `app/retrieve.py` for similarity thresholds and reranking.

## Troubleshooting

### Milvus Connection Issues
```bash
# Check if Milvus is healthy
docker compose ps milvus
docker compose logs milvus

# Verify connection
python -c "from pymilvus import connections; connections.connect('default', host='localhost', port='19530')"
```

### MinIO Access Problems
```bash
# Check MinIO status
docker compose logs minio

# Test connection
python -c "from minio import Minio; client = Minio('localhost:9000', 'minioadmin', 'minioadmin', secure=False); print(client.list_buckets())"
```

### Collection Schema Issues
Run migration scripts if schema changes:
```bash
python migrate_milvus_schema.py
python create_collection_fixed.py
```