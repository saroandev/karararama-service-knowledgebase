# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready Retrieval-Augmented Generation (RAG) system built with FastAPI, Milvus vector database, and MinIO object storage. The system processes PDF documents, creates embeddings, stores them in a vector database, and provides intelligent answers to queries using OpenAI's GPT models.

## Architecture

The system follows a modular architecture with clear separation of concerns:

### Directory Structure
- **`api/`**: Modern FastAPI-based REST API (production code)
  - `api/main.py`: Main FastAPI application entry point
  - `api/endpoints/`: Individual endpoint modules (query, ingest, documents, health)
  - `api/core/`: Core services (embeddings, Milvus manager, dependencies)
  - `api/utils/`: Utility functions and custom response handlers
  - `api/models/`: Pydantic models for requests/responses

- **`app/`**: Legacy application modules (being refactored)
  - `app/chunking/`: Modular text chunking strategies
    - `base.py`: Base chunker interface
    - `text_chunker.py`: Token-based chunking
    - `semantic_chunker.py`: Semantic similarity chunking
    - `hybrid_chunker.py`: Combined chunking strategies
  - `app/storage/`: Storage layer abstractions
    - `client.py`: MinIO client management
    - `documents.py`: Document storage operations
    - `chunks.py`: Chunk storage operations
    - `cache.py`: Storage caching layer
  - `app/config.py`: Central configuration management
  - `app/embed.py`: Embedding generation logic
  - `app/generate.py`: LLM response generation
  - `app/parse.py`: PDF parsing with PyMuPDF
  - `app/retrieve.py`: Vector search operations
  - `app/index.py`: Milvus indexing operations

- **Storage Layer**:
  - **Milvus**: Vector database for semantic search (port 19530)
  - **MinIO**: Object storage for PDF files and chunks (ports 9000, 9001)
  - **ETCD**: Metadata storage for Milvus
  - **Attu**: Milvus management UI (port 8000)

### Processing Pipeline
1. PDF ingestion → Text extraction (PyMuPDF)
2. Text chunking → Token-based chunking with overlap
3. Embedding generation → OpenAI text-embedding-3-small or multilingual-e5-small
4. Vector storage → Milvus collection with 1536 dimensions
5. Query processing → Semantic search + GPT-4o-mini generation

## Essential Commands

### Starting the System
```bash
# Start all Docker services
docker compose up -d

# Check service health
docker compose ps

# View logs for specific service
docker compose logs -f [milvus|minio|etcd|attu]

# Stop all services
docker compose down

# Clean restart with volume cleanup
docker compose down -v && docker compose up -d
```

### Running the API Server
```bash
# Development mode with auto-reload
python -m api.main

# Or using uvicorn directly with specific host/port
uvicorn api.main:app --reload --host 0.0.0.0 --port 8080

# Run from app directory (legacy)
python -m app.server
```

### Building and Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run linting (if configured)
python -m black app/ api/
python -m isort app/ api/

# Run type checking (if configured)
python -m mypy app/ api/
```

### Running Tests
```bash
# Run all tests with coverage report
pytest

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests requiring services
pytest -m docker        # Docker-dependent tests

# Run with verbose output and specific file
pytest -v tests/unit/test_config.py

# Generate HTML coverage report
pytest --cov=app --cov-report=html:test_output/htmlcov

# Run tests matching pattern
pytest -k "test_embedding"
```

### Streamlit UI
```bash
# Run the chat interface
streamlit run streamlit_chat_app.py

# Or with specific port
streamlit run streamlit_chat_app.py --server.port 8501

# Using the shell script with environment setup
./run_streamlit.sh
```

## Key Implementation Details

### Milvus Collection Schema
The system uses a collection named `rag_chunks_1536` with the following fields:
- `id`: Primary key (VARCHAR, max_length=64)
- `chunk_text`: Text content (VARCHAR, max_length=65535)
- `document_id`: Document reference (VARCHAR, max_length=255)
- `page_number`: Page reference (INT64)
- `chunk_index`: Chunk order (INT64)
- `embedding`: Vector field (FLOAT_VECTOR, dim=1536)
- `metadata`: JSON field for additional document metadata
- Indexes: HNSW index on embedding field with M=8, efConstruction=64

### Chunking Strategies
The system supports multiple chunking strategies:
- **TextChunker**: Token-based chunking with configurable size and overlap
- **SemanticChunker**: Groups text by semantic similarity
- **DocumentChunker**: Structure-aware chunking for documents
- **HybridChunker**: Combines multiple strategies

Default configuration uses token-based chunking with:
- Chunk size: 500 tokens
- Overlap: 100 tokens
- Using tiktoken for accurate token counting

### API Endpoints
- `GET /health`: System health check with service status
- `POST /ingest`: Upload and process PDF documents
  - Accepts: multipart/form-data with PDF file
  - Returns: document_id and processing statistics
- `POST /query`: Query the knowledge base
  - Body: `{"question": "...", "top_k": 5, "use_reranker": false}`
  - Returns: answer with sources and scores
- `GET /documents`: List all documents with metadata
- `DELETE /documents/{document_id}`: Delete document and its chunks

### Environment Variables
Required configuration in `.env`:
```env
# OpenAI Configuration (required)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini  # Generation model

# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=rag_chunks_1536
MILVUS_INDEX_TYPE=HNSW

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=rag-documents
MINIO_SECURE=False

# Embedding Configuration
EMBEDDING_PROVIDER=openai  # or 'local' for sentence-transformers
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
EMBEDDING_BATCH_SIZE=100

# Chunking Parameters
CHUNK_SIZE=500
CHUNK_OVERLAP=100
CHUNKING_STRATEGY=text  # text, semantic, document, or hybrid

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080

# Query Configuration
QUERY_TOP_K=5
QUERY_SCORE_THRESHOLD=0.7
USE_RERANKER=false
```

## Development Workflow

### Making API Changes
1. Add/modify endpoints in `api/endpoints/`
2. Update Pydantic models in `api/models/` if needed
3. Core services go in `api/core/`
4. Add corresponding tests in `tests/unit/` and `tests/integration/`
5. Run `pytest -m unit` before committing

### Working with Storage
- MinIO operations are in `app/storage/client.py`
- Milvus operations are in `api/core/milvus_manager.py`
- Document management is in `app/storage/documents.py`
- Chunk management is in `app/storage/chunks.py`

### Debugging Tips
```bash
# Check if Docker services are healthy
docker compose ps

# View Milvus logs for connection issues
docker compose logs -f milvus

# Access service UIs
# - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
# - Milvus Attu: http://localhost:8000
# - API Docs: http://localhost:8080/docs
# - Streamlit UI: http://localhost:8501

# Test Milvus connection
python -c "from pymilvus import connections; connections.connect('default', host='localhost', port='19530'); print('Connected!')"

# Test MinIO connection
python -c "from minio import Minio; client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False); print('Connected!')"

# Check collection schema
python -c "
from pymilvus import connections, Collection
connections.connect('default', host='localhost', port='19530')
col = Collection('rag_chunks_1536')
for field in col.schema.fields:
    print(f'{field.name}: {field.dtype.name}')
"

# Test embedding generation
python -c "from app.embed import generate_embedding; print(len(generate_embedding('test')))"
```

### Common Issues and Solutions

**Port conflicts**:
```bash
# Check if ports are in use
lsof -i :8080,9000,9001,19530,8000

# Kill process using port
kill -9 $(lsof -t -i:8080)
```

**Milvus collection errors**:
```bash
# Connect to Milvus and check/recreate collection
python -c "
from pymilvus import connections, utility, Collection
connections.connect('default', host='localhost', port='19530')
if utility.has_collection('rag_chunks_1536'):
    Collection('rag_chunks_1536').drop()
print('Collection cleared')
"
```

**Docker memory issues**:
```bash
# Increase Docker Desktop memory to at least 8GB
# Clean up unused resources
docker system prune -a --volumes
```

## Testing Strategy

The project uses pytest with markers for test organization:
- `unit`: Fast, isolated unit tests
- `integration`: Tests requiring service connections
- `docker`: Tests requiring Docker services running
- `api`: API endpoint tests
- `storage`: Storage layer tests (Milvus/MinIO)
- `embedding`: Embedding generation tests
- `chunk`: Text chunking tests

Test output is generated in `test_output/` with HTML coverage reports.

### Running Specific Test Suites
```bash
# Only storage-related tests
pytest -m storage

# API tests with verbose output
pytest -m api -v

# Integration tests with Docker services
docker compose up -d
pytest -m docker

# Run single test file
pytest tests/unit/test_config.py::TestConfig::test_load_config

# Run tests with parallel execution
pytest -n auto

# Run tests with debug output
pytest -vvs --log-cli-level=DEBUG
```

## Important Notes

- The system requires OpenAI API key for embeddings and generation
- Docker services must be running for full functionality
- The API server defaults to port 8080 when run standalone
- Collection schema must match the embedding dimension (1536 for OpenAI)
- Use the `api/` module for new endpoints, avoid modifying legacy `app/` files unless necessary
- The refactoring branch contains the latest modular improvements
- Python 3.9+ is required for all components
- The system uses tiktoken for accurate token counting
- Milvus requires at least 4GB RAM for optimal performance