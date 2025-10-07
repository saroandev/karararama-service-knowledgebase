# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready Retrieval-Augmented Generation (RAG) system built with FastAPI, Milvus vector database, and MinIO object storage. The system processes PDF documents (particularly Turkish legal documents), creates embeddings, stores them in a vector database, and provides intelligent answers to queries using OpenAI's GPT models.

**Key Feature**: Full JWT-based authentication and authorization integrated with OneDocs Auth Service, including permission-based access control, credit tracking, and usage logging.

## Architecture

The system follows a modular architecture with clear separation of concerns:

### Directory Structure
- **`api/`**: Modern FastAPI-based REST API (production code)
  - `api/main.py`: Main FastAPI application entry point with auth exception handlers
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
  - `app/core/validation/`: Document validation system
    - `document_validator.py`: Comprehensive validation layer
    - `content_analyzer.py`: Content quality analysis
    - `type_detector.py`: Document type detection
    - `metadata_extractor.py`: Metadata extraction
  - `app/core/auth.py`: JWT authentication and permission checking
  - `app/core/exceptions.py`: Custom auth exceptions
  - `app/services/auth_service.py`: Auth service client for usage tracking
  - `app/pipelines/`: End-to-end processing pipelines
    - `ingest_pipeline.py`: Document ingestion workflow
    - `query_pipeline.py`: Query processing workflow
  - `app/config/`: Configuration management
    - `settings.py`: Central configuration with auth settings

- **`schemas/`**: Pydantic models for validation
  - Centralized schema definitions for API requests/responses
  - Validation schemas

- **`streamlit-frontend/`**: Streamlit-based chat interface
- **`tests/`**: Comprehensive test suite
  - `tests/unit/`: Unit tests
  - `tests/integration/`: Integration tests requiring Docker services
  - `tests/conftest.py`: Shared test fixtures
  - Uses pytest markers: `unit`, `integration`, `docker`, `api`, `storage`, `embedding`, `chunk`

- **`models/`**: Local model cache directory

### Storage Layer
- **Milvus**: Vector database for semantic search (port 19530)
- **MinIO**: Object storage for PDF files and chunks (ports 9000, 9001)
- **ETCD**: Metadata storage for Milvus
- **Attu**: Milvus management UI (port 8000)

#### MinIO Multi-Tenant Structure
The system uses organization-based bucket isolation with folder-based user separation:

**Bucket Naming**: `org-{organization_id}` (one bucket per organization)

**Folder Structure**:
- **Private (User-specific)**:
  - Documents: `users/{user_id}/docs/{document_id}/{filename}.pdf`
  - Chunks: `users/{user_id}/chunks/{document_id}/{chunk_id}.json`
  - Metadata: `users/{user_id}/docs/{document_id}/{document_id}_metadata.json`

- **Shared (Organization-wide)**:
  - Documents: `shared/docs/{document_id}/{filename}.pdf`
  - Chunks: `shared/chunks/{document_id}/{chunk_id}.json`
  - Metadata: `shared/docs/{document_id}/{document_id}_metadata.json`

**Example Path**:
```
org-696e4ef0-9470-4425-ba80-43d94a48a4c1/
  └── users/
      └── 17d0faab-0830-4007-8ed6-73cfd049505b/
          ├── docs/
          │   └── doc_ea8b12a5a9e054b0/
          │       ├── icra_ve_iflas_kanunu.pdf
          │       └── doc_ea8b12a5a9e054b0_metadata.json
          └── chunks/
              └── doc_ea8b12a5a9e054b0/
                  ├── doc_ea8b12a5a9e054b0_0000.json
                  └── doc_ea8b12a5a9e054b0_0001.json
```

**Legacy Buckets** (deprecated, not used in new code):
- `raw-documents`: Old document storage
- `rag-chunks`: Old chunk storage
- `pdf-bucket`: Old PDF storage

### Processing Pipeline
1. PDF ingestion → Text extraction (PyMuPDF)
2. Document validation → Quality checks, type detection, metadata extraction
3. Text chunking → Multiple strategies (token, semantic, document, hybrid)
4. Embedding generation → OpenAI or local models
5. Vector storage → Milvus collection
6. Query processing → Semantic search + reranking + GPT generation

## Authentication & Authorization

The system uses JWT-based authentication with OneDocs Auth Service and multi-tenant data isolation:

- **JWT Token Authentication**: Secure token-based auth with HTTPBearer
- **Permission System**: Resource:action format (e.g., "research:query", "research:ingest")
- **Multi-Tenant Isolation**: Organization-based data separation with private/shared scopes
- **Role-Based Access**: User roles (admin, user) with different capabilities
- **Data Access Control**: Fine-grained access to own_data and shared_data
- **Credit Tracking**: Automatic usage logging and credit consumption
- **Development Mode**: Set `REQUIRE_AUTH=false` for local development without auth
- **Swagger Integration**: Automatic 🔒 Authorize button in API docs

### User Context Structure
JWT tokens decode to a UserContext containing:
- `user_id`: Unique user identifier
- `email`: User email address
- `organization_id`: User's organization (for multi-tenant isolation)
- `role`: User role (admin, user)
- `remaining_credits`: Available credits
- `permissions`: List of resource:action permissions
- `data_access`: Access flags for own_data and shared_data

### Data Scope System
The system implements three data scopes:
- **PRIVATE**: User's personal documents (accessible only by owner)
- **SHARED**: Organization-wide documents (accessible by all org members)
- **ALL**: Query across both private and shared (based on access permissions)

See `auth-integration.md` for comprehensive integration guide.

## Essential Commands

### Starting the System
```bash
# Start all Docker services
docker compose up -d
# Or
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

### Running Streamlit Frontend
```bash
# Start Streamlit interface
make streamlit
# Or:
streamlit run streamlit-frontend/app.py --server.port 8501

# Run both API and Streamlit together
make run-all
```

### Building and Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest
# Or
make test

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests requiring services
pytest -m docker         # Docker-dependent tests
pytest -m api            # API endpoint tests
pytest -m storage        # Storage tests (Milvus/MinIO)

# Or use Makefile
make test-unit
make test-integration

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

### Multi-Tenant Architecture

The system implements organization-based multi-tenancy with data isolation:

**Scope Hierarchy:**
```
Organization (org_id)
  ├── Shared Scope (org-wide documents)
  │   └── Collection: rag_chunks_{org_id}_shared
  └── Private Scopes (per-user documents)
      ├── User 1: rag_chunks_{org_id}_private_{user1_id}
      ├── User 2: rag_chunks_{org_id}_private_{user2_id}
      └── ...
```

**Access Control:**
- Users can always access their PRIVATE scope (if `data_access.own_data = true`)
- Users can access org SHARED scope (if `data_access.shared_data = true`)
- Only ADMIN role can write/delete in SHARED scope
- Regular users can only write/delete in their PRIVATE scope

**Working with Scopes:**
```python
from schemas.api.requests.scope import DataScope, ScopeIdentifier

# Create scope identifier for private collection
private_scope = ScopeIdentifier(
    organization_id=user.organization_id,
    scope_type=DataScope.PRIVATE,
    user_id=user.user_id
)

# Create scope identifier for shared collection
shared_scope = ScopeIdentifier(
    organization_id=user.organization_id,
    scope_type=DataScope.SHARED
)

# Get scoped collection
collection = milvus_manager.get_collection(scope_id)
```

### Milvus Collection Schema
The system uses **scope-based collections** for multi-tenant isolation:

**Collection Naming Pattern:**
- Private: `rag_chunks_{org_id}_private_{user_id}`
- Shared: `rag_chunks_{org_id}_shared`

**Collection Fields:**
- `id`: Primary key (VARCHAR)
- `chunk_text`: Text content (VARCHAR)
- `document_id`: Document reference (VARCHAR)
- `page_number`: Page reference (INT64)
- `chunk_index`: Chunk order (INT64)
- `embedding`: Vector field (FLOAT_VECTOR, dimension 1536 for OpenAI)
- `metadata`: JSON field for additional document metadata (includes document_title, file_hash, created_at)
- Indexes: HNSW index on embedding field for fast similarity search

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

All endpoints except `/health` require JWT authentication.

- `GET /health`: System health check with service status
- `POST /ingest`: Upload and process PDF documents
  - Requires: `research:ingest` permission
  - Accepts: multipart/form-data with PDF file
  - Query params: `scope` (private/shared) determines where document is stored
  - Returns: document_id and processing statistics
  - Logs usage to auth service
- `POST /query`: Query the knowledge base
  - Requires: `research:query` permission
  - Body: `{"question": "...", "top_k": 5, "use_reranker": false, "scope": "all"}`
  - Query params: `scope` (private/shared/all) determines which collections to search
  - Returns: answer with sources and scores (filtered by min_relevance_score)
  - Logs usage to auth service
- `GET /documents`: List all documents with metadata
  - Query params: `scope` (private/shared/all) filters documents by scope
  - Returns: list of DocumentInfo with scope labels
- `DELETE /documents/{document_id}`: Delete document and its chunks
  - Query params: `scope` (private/shared) specifies which collection to delete from
  - Only admins can delete from shared scope
  - Removes from both Milvus and MinIO

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
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# LLM Configuration
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
OLLAMA_MODEL=qwen2.5:7b-instruct

# Chunking Configuration
CHUNK_SIZE=512
CHUNK_OVERLAP=50
CHUNK_METHOD=token

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080

# JWT Authentication (CRITICAL - must match Auth Service)
JWT_SECRET_KEY=dev-secret-key-min-32-characters-long-12345
JWT_ALGORITHM=HS256
REQUIRE_AUTH=true

# Auth Service Configuration
AUTH_SERVICE_URL=http://onedocs-auth:8001
AUTH_SERVICE_TIMEOUT=5

# Query Source Filtering Configuration
DEFAULT_MIN_RELEVANCE_SCORE=0.7
ENABLE_SOURCE_FILTERING=true
DEFAULT_MAX_SOURCES_IN_CONTEXT=5

# Logging
LOG_LEVEL=INFO
```

## Development Workflow

### Making API Changes
1. Add/modify endpoints in `api/endpoints/`
2. Update core services in `api/core/` if needed
3. Add schemas in `schemas/api/`
4. Add corresponding tests in `tests/unit/` and `tests/integration/`
5. Run `pytest -m unit` before committing
6. For protected endpoints, use `Depends(require_permission("resource", "action"))`
7. For scope-aware endpoints, accept `scope: DataScope` query parameter
8. Use `milvus_manager.get_collection(scope_id)` to get scoped collections

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

### Working with Authentication
1. Protected endpoints require `Depends(get_current_user)` or `Depends(require_permission("resource", "action"))`
2. Use permission format: `resource:action` (e.g., "research:query", "research:ingest")
3. Report usage with `auth_service.consume_usage()` after processing
4. Set `REQUIRE_AUTH=false` for local development without auth
5. JWT_SECRET_KEY must match the one in OneDocs Auth Service
6. UserContext contains `organization_id`, `role`, and `data_access` for multi-tenant operations
7. Always create `ScopeIdentifier` when accessing scoped collections
8. Check `user.data_access.own_data` and `user.data_access.shared_data` before operations

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

# Test authentication
# 1. Get token from auth service
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# 2. Use token in API request
curl -X POST http://localhost:8080/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "test"}'
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

**Authentication errors**:
```bash
# Verify JWT_SECRET_KEY matches auth service
grep JWT_SECRET_KEY .env

# Check auth service is running
curl http://localhost:8001/health

# For local dev without auth
echo "REQUIRE_AUTH=false" >> .env
```

## Testing Strategy

The project uses pytest with markers for test organization:
- `unit`: Fast, isolated unit tests
- `integration`: Tests requiring service connections
- `e2e`: End-to-end tests for complete workflows
- `docker`: Tests requiring Docker services running
- `api`: API endpoint tests
- `storage`: Storage layer tests (Milvus/MinIO)
- `embedding`: Embedding generation tests
- `chunk`: Text chunking tests
- `parse`: PDF parsing functionality tests
- `llm`: Tests that interact with LLM services
- `slow`: Tests that take longer to run

Test configuration is in `pytest.ini` with coverage reporting to `test_output/`.

Run tests before committing:
```bash
# Quick unit tests
pytest -m unit

# Integration tests only
pytest -m integration

# Exclude slow tests
pytest -m "not slow"

# Run specific category
pytest -m api

# Full test suite (requires Docker services)
pytest

# With coverage report
pytest --cov=app --cov-report=html:test_output/htmlcov
```

## Important Notes

- The system requires OpenAI API key for embeddings and generation (or local models via Ollama)
- Docker services must be running for full functionality
- The API server defaults to port 8080
- Python 3.9+ is required for all components
- The system is optimized for Turkish legal documents but works with any PDF
- Use Makefile commands when available for consistency
- **Authentication is enabled by default** - set `REQUIRE_AUTH=false` for local dev only
- JWT_SECRET_KEY must be identical to OneDocs Auth Service
- All endpoints (except `/health`) require valid JWT token
- Permissions use format: `resource:action` (e.g., "research:query", "research:ingest")
- **Multi-tenant isolation**: Each organization has separate Milvus collections (private and shared)
- **Scope parameter**: Most endpoints accept `scope` query param (private/shared/all)
- **Role-based deletion**: Only admins can delete from shared scope
- **Query filtering**: Sources are filtered by relevance score (configurable via DEFAULT_MIN_RELEVANCE_SCORE)
- The current branch is `feature/auth` - main branch for PRs is typically `main` or `master`
