# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready Retrieval-Augmented Generation (RAG) system built with FastAPI, Milvus vector database, and MinIO object storage. The system processes PDF documents, creates embeddings, stores them in a vector database, and provides intelligent answers to queries using OpenAI's GPT models.

## Architecture

The system follows a modular architecture with clear separation of concerns:

- **API Layer** (`api/`): FastAPI-based REST API with modular endpoints
  - `api/main.py`: Main FastAPI application entry point
  - `api/endpoints/`: Individual endpoint modules (query, ingest, documents, health)
  - `api/core/`: Core services (embeddings, Milvus manager, dependencies)
  - `api/utils/`: Utility functions and custom response handlers

- **Storage Layer**:
  - **Milvus**: Vector database for semantic search (port 19530)
  - **MinIO**: Object storage for PDF files and chunks (ports 9000, 9001)
  - **ETCD**: Metadata storage for Milvus

- **Processing Pipeline**:
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

# View logs
docker compose logs -f [service_name]
```

### Running the API Server
```bash
# Development mode with auto-reload
python -m api.main

# Or using uvicorn directly
uvicorn api.main:app --reload --host 0.0.0.0 --port 8080
```

### Running Tests
```bash
# Run all tests with coverage
pytest

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests
pytest -m docker        # Docker-dependent tests

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_config.py
```

### Streamlit UI
```bash
# Run the chat interface
streamlit run streamlit_chat_app.py
```

### Collection Management
```bash
# Create new Milvus collection with proper schema
python create_collection_fixed.py

# Migrate existing collection schema
python migrate_milvus_schema.py

# Verify chunk consistency
python verify_chunk_consistency.py
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

### API Endpoints
- `GET /health`: System health check
- `POST /ingest`: Upload and process PDF documents
- `POST /query`: Query the knowledge base
- `GET /documents`: List all documents
- `DELETE /documents/{document_id}`: Delete specific document

### Environment Variables
Critical configuration in `.env`:
- `OPENAI_API_KEY`: Required for embeddings and generation
- `MILVUS_HOST`, `MILVUS_PORT`: Vector database connection
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`: Object storage
- `EMBEDDING_MODEL`: Model selection (OpenAI or local)
- `CHUNK_SIZE`, `CHUNK_OVERLAP`: Text chunking parameters

## Development Workflow

### Adding New Features
1. Create feature branch from master
2. Implement changes in appropriate module (`api/endpoints/` for new endpoints)
3. Add unit tests in `tests/unit/`
4. Add integration tests if needed in `tests/integration/`
5. Run full test suite before committing

### Debugging Tips
- Check Docker service logs: `docker compose logs -f [service]`
- API logs are in real-time when running with `--reload`
- Milvus web UI available at http://localhost:8000 (Attu)
- MinIO console at http://localhost:9001 (admin/minioadmin)

### Common Issues
- **Port conflicts**: Check if ports 8080, 9000, 9001, 19530, 8000 are free
- **Memory issues**: Ensure Docker has at least 8GB RAM allocated
- **Connection errors**: Wait for all services to be healthy (use `docker compose ps`)
- **Collection errors**: Run `create_collection_fixed.py` to ensure proper schema

## Testing Strategy

The project uses pytest with comprehensive test coverage:
- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test component interactions
- **Docker tests**: Test with actual services running

Test output is generated in `test_output/` directory with HTML coverage reports.

## Important Notes

- The system requires OpenAI API key for embeddings and generation
- Docker services must be running for full functionality
- The API server can run standalone for development but needs Docker services for storage
- Collection schema must match the embedding dimension (1536 for OpenAI, configurable for others)
- Always use the `api/` module structure for new endpoints, don't modify legacy `app/` files