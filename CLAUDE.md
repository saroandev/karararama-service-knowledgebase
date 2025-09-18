# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready Retrieval-Augmented Generation (RAG) system built with FastAPI, Milvus vector database, and MinIO object storage. The system processes PDF documents (particularly Turkish legal documents), creates embeddings, stores them in a vector database, and provides intelligent answers to queries using OpenAI's GPT models.

## Architecture

The system follows a modular architecture with clear separation of concerns:

### Directory Structure
- **`api/`**: Modern FastAPI-based REST API (production code)
  - `api/main.py`: Main FastAPI application entry point
  - `api/endpoints/`: Individual endpoint modules (query, ingest, documents, health)
  - `api/core/`: Core services (embeddings, Milvus manager, dependencies)
  - `api/utils/`: Utility functions and custom response handlers

- **`app/`**: Comprehensive application modules with advanced features
  - `app/core/chunking/`: Modular text chunking strategies
    - `base.py`: Base chunker interface
    - `text_chunker.py`: Token-based chunking
    - `semantic_chunker.py`: Semantic similarity chunking
    - `document_chunker.py`: Document structure-aware chunking
    - `hybrid_chunker.py`: Combined chunking strategies
  - `app/core/storage/`: Storage layer abstractions
    - `client.py`: MinIO client management
    - `documents.py`: Document storage operations
    - `chunks.py`: Chunk storage operations
    - `cache.py`: Storage caching layer
  - `app/core/embeddings/`: Embedding providers
    - `openai_embeddings.py`: OpenAI embeddings
    - `local_embeddings.py`: Local sentence-transformers
  - `app/core/generation/`: LLM response generation
    - `openai_generator.py`: OpenAI GPT models
    - `ollama_generator.py`: Local Ollama models
  - `app/core/parsing/`: Document parsing
    - `pdf_parser.py`: PyMuPDF-based PDF extraction
  - `app/core/retrieval/`: Vector search and reranking
    - `vector_search.py`: Milvus vector search
    - `reranker.py`: Result reranking
    - `hybrid_retriever.py`: Combined retrieval strategies
  - `app/pipelines/`: End-to-end processing pipelines
    - `ingest_pipeline.py`: Document ingestion workflow
    - `query_pipeline.py`: Query processing workflow
  - `app/config/`: Configuration management
    - `settings.py`: Central configuration
    - `constants.py`: System constants
    - `validators.py`: Configuration validation

- **`streamlit-frontend/`**: Streamlit-based chat interface
- **`tests/`**: Comprehensive test suite with unit and integration tests
- **`models/`**: Local model cache directory

### Storage Layer
- **Milvus**: Vector database for semantic search (port 19530)
- **MinIO**: Object storage for PDF files and chunks (ports 9000, 9001)
- **ETCD**: Metadata storage for Milvus
- **Attu**: Milvus management UI (port 8000)

### Processing Pipeline
1. PDF ingestion → Text extraction (PyMuPDF)
2. Text chunking → Multiple strategies (token, semantic, document, hybrid)
3. Embedding generation → OpenAI or local models
4. Vector storage → Milvus collection
5. Query processing → Semantic search + reranking + GPT generation

## Essential Commands

### Starting the System
```bash
# Start all Docker services
docker compose up -d

# Or use Makefile
make docker-up

# Check service health
docker compose ps

# View logs for specific service
docker compose logs -f [milvus|minio|etcd|attu]

# Stop all services
docker compose down
# Or
make docker-down

# Clean restart with volume cleanup
docker compose down -v && docker compose up -d
# Or
make clean-all && make docker-up
```

### Running the API Server
```bash
# Development mode with auto-reload (recommended)
make run
# Or directly:
uvicorn api.main:app --reload --host 0.0.0.0 --port 8080

# Production mode with multiple workers
make run-prod
# Or:
uvicorn api.main:app --host 0.0.0.0 --port 8080 --workers 4

# Simple Python execution
python -m api.main
```

### Building and Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests requiring services
pytest -m docker        # Docker-dependent tests

# Or use Makefile
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests

# Run with coverage report
pytest --cov=app --cov-report=html:test_output/htmlcov

# Clean cache and temporary files
make clean
```

### Database Management
```bash
# Clean Milvus collection (if script exists)
python scripts/cleanup_milvus.py

# Or manually via Python
python -c "
from pymilvus import connections, utility, Collection
connections.connect('default', host='localhost', port='19530')
if utility.has_collection('rag_chunks'):
    Collection('rag_chunks').drop()
print('Collection cleared')
"
```

## Key Implementation Details

### Milvus Collection Schema
The system uses collections with the following fields:
- `id`: Primary key (VARCHAR)
- `chunk_text`: Text content (VARCHAR)
- `document_id`: Document reference (VARCHAR)
- `page_number`: Page reference (INT64)
- `chunk_index`: Chunk order (INT64)
- `embedding`: Vector field (FLOAT_VECTOR)
- `metadata`: JSON field for additional document metadata
- Indexes: HNSW index on embedding field

### Chunking Strategies
The system supports multiple chunking strategies:
- **TextChunker**: Token-based chunking with configurable size and overlap
- **SemanticChunker**: Groups text by semantic similarity
- **DocumentChunker**: Structure-aware chunking for documents
- **HybridChunker**: Combines multiple strategies

Default configuration:
- Chunk size: 512 tokens
- Overlap: 50 tokens
- Method: Token-based

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
# OpenAI Configuration
OPENAI_API_KEY=sk-...

# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=rag_chunks

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_DOCS=raw-pdfs
MINIO_BUCKET_CHUNKS=chunks
MINIO_SECURE=false

# Embedding Configuration
EMBEDDING_MODEL=intfloat/multilingual-e5-small
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# LLM Configuration
LLM_PROVIDER=openai
OLLAMA_MODEL=qwen2.5:7b-instruct

# Chunking Configuration
CHUNK_SIZE=512
CHUNK_OVERLAP=50
CHUNK_METHOD=token

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080

# Logging
LOG_LEVEL=INFO
```

## Development Workflow

### Making API Changes
1. Add/modify endpoints in `api/endpoints/`
2. Update core services in `api/core/` if needed
3. Add corresponding tests in `tests/unit/` and `tests/integration/`
4. Run `pytest -m unit` before committing

### Working with Storage
- MinIO operations are in `app/core/storage/client.py`
- Milvus operations are in `api/core/milvus_manager.py`
- Document management is in `app/core/storage/documents.py`
- Chunk management is in `app/core/storage/chunks.py`

### Adding New Features
1. For new chunking strategies: Extend `app/core/chunking/base.py`
2. For new embedding providers: Extend `app/core/embeddings/base.py`
3. For new LLM providers: Extend `app/core/generation/base.py`
4. For new parsers: Extend `app/core/parsing/base.py`

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

# Test Milvus connection
python -c "from pymilvus import connections; connections.connect('default', host='localhost', port='19530'); print('Connected!')"

# Test MinIO connection
python -c "from minio import Minio; client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False); print('Connected!')"

# Check collection schema
python -c "
from pymilvus import connections, Collection
connections.connect('default', host='localhost', port='19530')
col = Collection('rag_chunks')
for field in col.schema.fields:
    print(f'{field.name}: {field.dtype.name}')
"
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
# Recreate collection
make milvus-clean
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

Test configuration is in `pytest.ini` with coverage reporting to `test_output/`.

## Important Notes

- The system requires OpenAI API key for embeddings and generation (or local models via Ollama)
- Docker services must be running for full functionality
- The API server defaults to port 8080
- Python 3.9+ is required for all components
- The system is optimized for Turkish legal documents but works with any PDF
- Use Makefile commands when available for consistency