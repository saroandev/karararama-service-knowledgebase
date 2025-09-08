# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Overview

This is a production-ready RAG (Retrieval-Augmented Generation) pipeline built with FastAPI, Milvus vector database, MinIO object storage, and OpenAI models. The system processes PDF documents and provides intelligent Q&A capabilities with source citations.

## Key Architecture Components

- **FastAPI Server** (`app/server.py`): Development server with comprehensive API endpoints
- **Production Server** (`production_server.py`): Streamlined production-ready server with persistent storage
- **Processing Pipeline**: PDF parsing → text chunking → embedding generation → vector indexing
- **Storage Layer**: Milvus (vectors) + MinIO (objects) + ETCD (metadata)
- **Docker Services**: All components containerized with health checks

## Essential Commands

### Development & Testing

```bash
# Start all Docker services
docker compose up -d

# Check service status
docker compose ps

# View logs (all services)
docker compose logs -f

# View specific service logs
docker compose logs -f milvus
docker compose logs -f app

# Stop all services
docker compose down

# Rebuild and restart
docker compose down && docker compose up -d --build
```

### Production Server

```bash
# Run production server (recommended for deployment)
PYTHONPATH=/Users/ugur/Desktop/onedocs-rag uvicorn production_server:app --host 0.0.0.0 --port 8080 --reload

# Run development server
PYTHONPATH=/Users/ugur/Desktop/onedocs-rag uvicorn app.server:app --host 0.0.0.0 --port 8080 --reload

# Health check
curl http://localhost:8080/health
```

### Testing & Validation

```bash
# Basic system validation
python simple_validation.py

# Docker services test
python test_docker_services.py

# Full integration test
python integration_test.py

# Test with sample PDF
curl -X POST "http://localhost:8080/ingest" -F "file=@POSTA GEZİCİ PERSONELİNE VERİLECEK HARCIRAH TÜZÜĞÜ_78670.pdf"

# Query test
curl -X POST "http://localhost:8080/query" -H "Content-Type: application/json" -d '{"question": "Bu dokümanda ne anlatılıyor?"}'
```

### Development Setup

```bash
# Python environment (if not using Docker)
python -m venv venv
source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# Set Python path for local development
export PYTHONPATH=/Users/ugur/Desktop/onedocs-rag

# Code formatting (if needed)
black app/
isort app/
```

## Critical Configuration

### Environment Setup
- Copy `.env.example` to `.env` and configure OpenAI API key
- Current config uses `intfloat/multilingual-e5-small` for embeddings but production server uses OpenAI embeddings
- Production server uses Milvus collection `rag_production_v1`
- Development server uses collection name from `.env` (`rag_chunks`)

### Port Configuration
- **FastAPI**: 8080
- **Streamlit Frontend**: 8501
- **MinIO**: 9000 (API), 9001 (Console)
- **Milvus**: 19530 (gRPC), 9091 (metrics)
- **Attu (Milvus GUI)**: 8000
- **ETCD**: 2379

## Code Structure & Patterns

### Main Application Modules (`app/`)
- `config.py`: Centralized configuration management
- `storage.py`: MinIO operations for document storage
- `parse.py`: PDF text extraction using PyMuPDF
- `chunk.py`: Text chunking strategies (token-based)
- `embed.py`: Embedding generation (supports both OpenAI and local models)
- `index.py`: Milvus vector database operations
- `retrieve.py`: Vector search and reranking
- `generate.py`: LLM response generation
- `ingest.py`: Complete ingestion pipeline orchestration
- `server.py`: FastAPI application with comprehensive endpoints

### Server Architecture
- **Development Server** (`app/server.py`): Full-featured with WebSocket support, background tasks, comprehensive API
- **Production Server** (`production_server.py`): Simplified, optimized for production use with direct Milvus operations

### Key Design Patterns
- All processing uses async/await patterns
- Progress tracking via WebSocket for long operations
- Comprehensive error handling with HTTP status codes
- Modular pipeline components for easy maintenance
- Docker-first deployment strategy

## Data Flow

### Ingestion Pipeline
1. PDF upload via FastAPI multipart/form-data
2. PyMuPDF parsing with metadata extraction
3. Text chunking (512 tokens, 50 overlap default)
4. Embedding generation (OpenAI text-embedding-3-small)
5. Vector storage in Milvus with metadata
6. Raw text storage in MinIO

### Query Pipeline  
1. Question embedding generation
2. Vector similarity search in Milvus (top-k)
3. Optional reranking with BGE-reranker-v2-m3
4. Context assembly with retrieved chunks
5. LLM generation with source citation

## Production Readiness Status

### ✅ Ready Components
- Docker containerization with health checks
- Production server optimized for deployment
- Persistent storage (Milvus + MinIO)
- API key management via environment variables
- Comprehensive logging and error handling
- CORS middleware configured
- OpenAI API integration stable

### ⚠️ Production Gaps Identified
- No authentication/authorization system
- Rate limiting not implemented  
- No input validation for malicious content
- Missing backup/restore procedures
- No monitoring/metrics collection
- SSL/TLS configuration not included
- No graceful shutdown handling

### 🛠️ Deployment Requirements
- Minimum 8GB RAM (16GB recommended)
- Docker & Docker Compose v2.0+
- Valid OpenAI API key with sufficient credits
- Stable internet connection for API calls
- 20GB+ disk space for data storage

## Testing & Validation

Sample PDF exists in repository: `POSTA GEZİCİ PERSONELİNE VERİLECEK HARCIRAH TÜZÜĞÜ_78670.pdf`

Test results are stored in `test_output/` directory with JSON reports for:
- Document processing results
- System integration tests  
- Performance benchmarks

## Common Operations

### Adding New Features
1. Implement in appropriate module (`app/`)
2. Add corresponding endpoint to `server.py`
3. Update `production_server.py` if needed
4. Test with Docker environment
5. Update documentation

### Debugging Issues
1. Check service health: `curl http://localhost:8080/health`
2. View logs: `docker compose logs -f [service_name]`
3. Test individual components with validation scripts
4. Use Attu GUI for Milvus debugging: http://localhost:8000
5. Use MinIO console for storage debugging: http://localhost:9001

### Performance Optimization
- Milvus indexing parameters in `app/index.py`
- Chunking strategy configuration in `app/chunk.py`
- Embedding batch processing in `app/embed.py`
- Connection pooling and resource management

## Model & API Dependencies

- **OpenAI Models**: gpt-4o-mini (generation), text-embedding-3-small (embeddings)
- **Local Models**: intfloat/multilingual-e5-small, BAAI/bge-reranker-v2-m3
- **Embedding Dimensions**: 1536 (OpenAI), variable for local models
- **Token Limits**: 512 chunks with 50 token overlap

## Frontend & User Interface

### Streamlit Web Application
- **Location**: `streamlit_app.py` (root directory)
- **Name**: OneDocs Assistant 📚
- **Port**: 8501 (http://localhost:8501)
- **Features**:
  - PDF document upload and processing
  - Real-time chat interface with AI responses
  - Source citation display with page numbers and scores
  - System health monitoring
  - Clean, minimal UI design matching Streamlit's native styling

### Streamlit Commands
```bash
# Start Streamlit frontend
streamlit run streamlit_app.py --server.port 8501

# Start with backend services
docker compose up -d etcd minio milvus attu  # Infrastructure
PYTHONPATH=/Users/ugur/Desktop/onedocs-rag uvicorn production_server:app --host 0.0.0.0 --port 8080 --reload &
streamlit run streamlit_app.py --server.port 8501
```

### Docker Configuration
- **Service**: `streamlit` in docker-compose.yml
- **Container**: `rag-streamlit`
- **Dockerfile**: `Dockerfile.streamlit`
- **Environment**: `API_BASE_URL=http://app:8080`
- **Dependencies**: Depends on FastAPI backend (`app` service)

### UI Components
1. **Header**: Application title and description
2. **Sidebar**: 
   - PDF file upload functionality
   - Uploaded documents list
   - System health checker
   - Chat history clear button
3. **Main Area**: 
   - Chat message history
   - Real-time message input
   - Source citations with document references
4. **Footer**: System information

### Key Features
- **File Upload**: Drag-and-drop PDF processing via `/ingest` API
- **Chat Interface**: Real-time Q&A using `/query` API
- **Source Display**: Shows document title, page number, relevance score, and text preview
- **Error Handling**: Connection errors and API failures gracefully handled
- **Session State**: Maintains chat history and uploaded files across page refreshes

### Styling & Design
- **Color Scheme**: Minimalist design using Streamlit's default colors
- **Chat Messages**: Styled boxes with sidebar-matching background (#262730)
- **Typography**: Native Streamlit fonts for optimal readability
- **Layout**: Wide layout with expanded sidebar by default
- **Responsive**: Works on desktop and mobile devices

### Integration with Backend
- **Health Endpoint**: `/health` - System status monitoring
- **Upload Endpoint**: `/ingest` - PDF document processing
- **Query Endpoint**: `/query` - AI question answering with sources
- **Error Handling**: Displays backend errors and connection issues to user

### Troubleshooting
- **Font Issues**: Use native Streamlit components instead of custom CSS
- **API Connection**: Ensure backend server is running on port 8080
- **Docker Integration**: Streamlit service depends on app service being healthy
- **Page Refresh**: Use `st.rerun()` for immediate UI updates

### Development Notes
- **Protobuf Compatibility**: Fixed by using pymilvus==2.3.4 and grpcio==1.58.0
- **Dependencies**: All required packages listed in requirements.txt
- **Environment**: Uses `API_BASE_URL` environment variable for backend connection