# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**OneDocs Service KnowledgeBase** is an enterprise-grade multi-tenant RAG (Retrieval-Augmented Generation) system built with FastAPI, Milvus (vector database), MinIO (object storage), and OpenAI. It enables organizations to create, manage, and intelligently query their own knowledge bases with strong data isolation and JWT-based authentication.

## Common Commands

### Development
```bash
# Start development server with auto-reload
make run

# Run API directly
uvicorn api.main:app --reload --host 0.0.0.0 --port 8080

# Production mode with 4 workers
make run-prod
```

### Docker Services
```bash
# Start all services (Milvus, MinIO, PostgreSQL, ETCD, Attu)
docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f

# Restart specific service
docker compose restart app

# Check service status
docker compose ps
```

### Testing
```bash
# Run all tests
make test

# Run only unit tests (fast, no Docker)
make test-unit

# Run integration tests (requires Docker)
make test-integration

# Generate coverage report
pytest --cov=app --cov=api --cov-report=html:test_output/htmlcov
```

### Database Management
```bash
# Clean Milvus collections
make milvus-clean

# Clean all cache and test artifacts
make clean

# Clean everything including Docker volumes
make clean-all
```

### Rebuild Docker Image
```bash
# After api/ or schemas/ changes (they're copied during build)
docker compose build app
docker compose up -d

# Full rebuild without cache
docker compose build --no-cache app
docker compose up -d

# Note: app/ folder is volume-mounted, changes reflect immediately
```

## High-Level Architecture

### Multi-Tenant Data Isolation

The system implements strict data isolation at three levels:

1. **Organization Level**: Each org has its own MinIO bucket (`org-{org_id}`)
2. **User Level**: Private data scoped to individual users
3. **Scope Types**:
   - `PRIVATE`: User's private documents (only owner can access)
   - `SHARED`: Organization-wide shared documents (all members can access)
   - `MEVZUAT`: External legislation database (read-only, via external service)
   - `KARAR`: External court decisions database (read-only, via external service)

**Collection Naming Convention:**
- Private default: `user_{user_id}_chunks_1536`
- Private collection: `user_{user_id}_col_{collection_name}_chunks_1536`
- Shared default: `org_{org_id}_shared_chunks_1536`
- Shared collection: `org_{org_id}_col_{collection_name}_chunks_1536`

**Important**: UUIDs are sanitized by replacing `-` with `_` for Milvus compatibility. Collection names with Turkish characters (ş, ğ, ı, ö, ü, ç) are auto-converted to ASCII equivalents.

**MinIO Folder Structure:**
```
org-{org_id}/
├── users/{user_id}/
│   ├── docs/                    # Default space
│   ├── chunks/
│   └── collections/{name}/      # Named collections
│       ├── docs/
│       └── chunks/
└── shared/
    ├── docs/                    # Default shared
    ├── chunks/
    └── collections/{name}/      # Named shared collections
```

### Orchestrator Pattern

The system uses two main orchestrators for processing pipelines:

#### IngestOrchestrator (`app/core/orchestrator/ingest_orchestrator.py`)
Coordinates document ingestion through sequential stages:
1. **ValidationStage**: Format check, size limits, duplicate detection
2. **ParsingStage**: PyMuPDF text extraction
3. **ChunkingStage**: Token-based splitting (512 tokens, 50 overlap)
4. **EmbeddingStage**: OpenAI embeddings (1536 dimensions)
5. **IndexingStage**: Milvus HNSW index insertion
6. **StorageStage**: MinIO upload (PDF + chunks)
7. **ConsumeStage**: Auth service usage tracking

Each stage implements the `PipelineStage` interface and receives a `PipelineContext` containing all shared state.

#### QueryOrchestrator (`app/core/orchestrator/orchestrator.py`)
Coordinates multi-source query processing with parallel execution:
1. Analyzes `sources` and `collections` parameters
2. Creates appropriate handlers:
   - `CollectionServiceHandler`: Searches Milvus collections
   - `ExternalServiceHandler`: Queries MEVZUAT/KARAR external services
3. Executes all handlers in parallel using `asyncio.gather`
4. `ResultAggregator` merges and deduplicates results
5. Generates LLM response with source citations

**Key Behavior**: If `collections` is not specified or empty, and `sources` only contains external sources (MEVZUAT/KARAR), the system only searches external services. If neither `collections` nor external `sources` are specified, the system enters **LLM-only mode** - answering questions using GPT's training data without RAG retrieval.

### Conversation History (`app/core/conversation.py`)

PostgreSQL-based chat history with SQLAlchemy:
- **Table**: `conversation_log` (auto-created by `migrations/init.sql`)
- **Conversation ID**: UUID format `conv-{uuid}`, passed in request or auto-generated
- **Context Injection**: Last 10 messages automatically sent to LLM for multi-turn awareness
- **Storage**: User questions and assistant answers with metadata (tokens, processing time, sources)

**Methods**:
- `create_new_conversation()`: Generates new conversation ID
- `save_message()`: Stores user/assistant messages
- `get_context_for_llm()`: Retrieves last N messages formatted for GPT

**PostgreSQL Configuration**:
- Host port: 5431 (external access)
- Container port: 5432 (internal Docker network)
- Environment variable: Use `POSTGRES_PORT=5432` in `docker-compose.yml` for app service (internal networking)

### Authentication & Authorization

**JWT Token Flow:**
1. Client obtains JWT token from OneDocs Auth Service
2. Token contains: `user_id`, `organization_id`, `role`, `permissions`, `data_access`, `remaining_credits`
3. Every endpoint (except `/health`) validates token via `get_current_user()` dependency
4. Fine-grained permissions checked via `require_permission(resource, action)` decorator

**Permission System:**
- Format: `{resource}:{action}` (e.g., `research:query`, `research:ingest`)
- Supports wildcards: `*`, `admin:*`, `research:*`
- O(1) permission lookup using cached set-based implementation in `UserContext.has_permission()`

**Data Access Flags** (in JWT):
- `own_data`: Can access private documents
- `shared_data`: Can access organization shared documents
- `all_users_data`: Admin-only, access all org users' data

**Development Mode:**
Set `REQUIRE_AUTH=false` in `.env` to bypass authentication (returns mock admin user).

### API Endpoint Pattern

All endpoints follow this structure:
1. JWT authentication via `Depends(get_current_user)`
2. Permission check via `Depends(require_permission(resource, action))`
3. Scope resolution using `UserContext.organization_id` and `user_id`
4. Automatic multi-tenant isolation enforced by `ScopeIdentifier`

Example:
```python
@router.post("/chat/process", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    user: UserContext = Depends(get_current_user)  # Auto JWT validation
):
    # Business logic - user context ensures data isolation
    ...
```

### Key Services

**Milvus Manager** (`api/core/milvus_manager.py`):
- Vector database connection management
- Collection creation with HNSW index (M=16, efConstruction=256)
- Multi-tenant collection isolation
- Metadata filtering on `user_id`, `organization_id`, `scope`

**Storage Manager** (`app/core/storage/minio_manager.py`):
- MinIO client singleton
- Bucket creation and management
- Document upload/download with metadata
- Folder-based isolation within buckets

**Embedding Service** (`api/core/embeddings.py`):
- OpenAI `text-embedding-3-small` (1536 dimensions)
- Batch embedding generation for performance
- Error handling and retry logic

**LLM Generation** (`app/core/generation/`):
- GPT-4o-mini for answer generation
- Prompt templates in `app/core/orchestrator/prompts.py`
- Supports tone (resmi/samimi/teknik/öğretici) and language (tr/eng) options
- Source citations in format `[Kaynak 1]`, `[Kaynak 2]`

## Known Issues & Quirks

### ~~Pymilvus Collection Creation Exception~~ (FIXED in 2025-10-18)

**Problem**: In pymilvus 2.3.4, `Collection(name, schema)` internally calls `has_collection()` which throws `MilvusException` when the collection doesn't exist during creation attempts. This was incompatible with Milvus server v2.6.1.

**Solution**: Upgrade pymilvus client to match Milvus server version:
- Milvus server: v2.6.1 (docker image: `milvusdb/milvus:v2.6.1`)
- pymilvus client: v2.6.2 (requirements.txt)

**Key changes in requirements.txt**:
```python
pymilvus==2.6.2                      # Updated from 2.3.4 to match server version
python-dotenv>=1.0.1,<2.0.0          # Updated for pymilvus 2.6.2 dependency
protobuf>=5.27.2                     # Updated for pymilvus 2.6.2 dependency
```

**After upgrade**: Collection creation works perfectly without exceptions. The `Collection(name, schema)` constructor now properly creates collections in Milvus 2.6.x.

**Rebuild Required**:
```bash
docker compose build app
docker compose up -d
```

**Testing**:
```python
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType
# This now works without errors in pymilvus 2.6.2:
collection = Collection(name="test_collection", schema=schema)
```

## Environment Configuration

Critical environment variables (see `.env` or `knowledgebase.yaml` for Kubernetes):

**Required for operation:**
- `OPENAI_API_KEY`: OpenAI API key for embeddings and LLM
- `JWT_SECRET_KEY`: Must match OneDocs Auth Service (min 32 chars)
- `MILVUS_HOST`, `MILVUS_PORT`: Vector database connection
- `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: Object storage
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: Conversation history database

**Auth configuration:**
- `REQUIRE_AUTH`: Set to `false` for local dev without auth service
- `AUTH_SERVICE_URL`: OneDocs Auth Service endpoint
- `JWT_ALGORITHM`: Must be `HS256` (matching auth service)

**Docker Networking Note:**
When running in Docker Compose, use **service names** for `*_HOST` variables:
- `MILVUS_HOST=milvus` (not `localhost`)
- `MINIO_ENDPOINT=minio:9000` (not `localhost:9000`)
- `POSTGRES_HOST=postgres` (not `localhost`)

Use **internal container ports** for `*_PORT` variables:
- `MILVUS_PORT=19530`
- `POSTGRES_PORT=5432` (not 5431, which is the host-mapped port)

**Kubernetes deployment:**
Use `knowledgebase.yaml` for ConfigMap (non-sensitive) and Secret (sensitive) separation.

## Project Structure Notes

**api/**: FastAPI application layer
- `endpoints/`: REST API endpoints (`query.py`, `collections.py`, `ingest.py`, `conversations.py`)
- `core/`: Infrastructure services (`milvus_manager.py`, `embeddings.py`, `dependencies.py`)

**app/**: Business logic layer
- `core/orchestrator/`: Orchestrator pattern implementation
- `core/auth.py`: JWT authentication and permission system
- `core/conversation.py`: PostgreSQL conversation history manager
- `core/storage/`: MinIO storage management
- `pipelines/`: Legacy pipeline implementations (being replaced by orchestrators)

**schemas/**: Pydantic data models
- `api/requests/`: Request validation models (`query.py`, `scope.py`, `collection.py`)
- `api/responses/`: Response models (`query.py`, `conversation.py`, `collection.py`)
- `config/`: Configuration schemas (uses `pydantic-settings`)

**migrations/**: Database migrations
- `init.sql`: PostgreSQL schema initialization (creates `conversation_log` table)

**Important**: The `pydantic-settings` package is required (added in requirements.txt) for `BaseSettings` used in configuration management.

## Testing Strategy

- **Unit tests** (`tests/unit/`): Fast, no external dependencies, test individual functions
- **Integration tests** (`tests/integration/`): Require Docker services, test full workflows
- Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`
- Shared fixtures in `tests/conftest.py`

## Common Development Patterns

### Adding a new endpoint:
1. Create request/response schemas in `schemas/api/`
2. Define endpoint in `api/endpoints/`
3. Add permission check: `user: UserContext = Depends(require_permission("resource", "action"))`
4. Use `ScopeIdentifier` for multi-tenant isolation
5. Register router in `api/main.py`

### Adding a new ingestion stage:
1. Extend `PipelineStage` base class in `app/core/orchestrator/stages/`
2. Implement `execute(context: PipelineContext)` method
3. Update context with stage results
4. Register stage in `IngestOrchestrator.execute_pipeline()`

### Working with collections:
- Collection names support Turkish characters (auto-sanitized to ASCII for Milvus)
- Always specify scope (`private` or `shared`) when creating/accessing collections
- Use `ScopeIdentifier.get_collection_name()` to generate proper Milvus collection names
- Collection metadata stored in MinIO as JSON alongside documents

## Debugging Tips

**Check Milvus connection:**
```python
from pymilvus import connections, utility
connections.connect('default', host='localhost', port='19530')
print(utility.list_collections())
```

**Check MinIO buckets:**
```python
from minio import Minio
client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False)
print(list(client.list_buckets()))
```

**View Docker logs:**
```bash
docker compose logs -f milvus    # Milvus logs
docker compose logs -f minio     # MinIO logs
docker compose logs -f app       # API logs
```

**Access web interfaces:**
- Swagger UI: http://localhost:8080/docs (use 🔒 Authorize button for JWT)
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
- Milvus Attu: http://localhost:8000 (visual DB management)

**PostgreSQL access:**
```bash
# Connect to database
docker exec -it rag-postgres psql -U raguser -d rag_database

# Check conversation history
SELECT conversation_id, role, content, created_at
FROM conversation_log
ORDER BY created_at DESC
LIMIT 10;
```

## Performance Considerations

- Vector search in Milvus: <100ms typical
- Embedding generation (OpenAI API): ~500ms per batch
- LLM answer generation: 1-3 seconds
- Total query time: <5 seconds target
- HNSW index parameters tuned for accuracy/speed balance (M=16, efConstruction=256)
- Parallel handler execution in QueryOrchestrator reduces latency for multi-source queries

## Security Notes

- All user input validated via Pydantic models
- SQL injection not applicable (no SQL database for user data)
- JWT tokens expire based on auth service configuration
- Scope isolation automatically enforced - users cannot bypass multi-tenant boundaries
- MinIO and Milvus credentials should be changed in production
- HTTPS required in production (configure via reverse proxy)
