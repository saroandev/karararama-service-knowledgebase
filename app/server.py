import logging
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.ingest import ingestion_pipeline, IngestionProgress
from app.retrieve import retriever
from app.generate import llm_generator
from app.storage import storage
from app.index import milvus_indexer
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG Pipeline API",
    description="Document ingestion and retrieval system with LLM generation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Pydantic models
class QueryRequest(BaseModel):
    question: str = Field(..., description="Question to ask")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    use_reranker: bool = Field(default=True, description="Whether to use reranking")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Search filters")
    stream: bool = Field(default=False, description="Stream response")

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class IngestRequest(BaseModel):
    chunk_strategy: str = Field(default="token", description="Chunking strategy")
    chunk_size: int = Field(default=512, ge=100, le=2000, description="Chunk size")
    chunk_overlap: int = Field(default=50, ge=0, le=500, description="Chunk overlap")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

class DocumentResponse(BaseModel):
    documents: List[Dict[str, Any]]
    total: int
    page: int
    pages: int

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Progress callback for WebSocket updates
def progress_callback(progress: IngestionProgress):
    message = {
        "type": "progress",
        "stage": progress.stage,
        "progress": progress.progress,
        "message": progress.message,
        "current_step": progress.current_step,
        "total_steps": progress.total_steps,
        "document_id": progress.document_id,
        "error": progress.error
    }
    asyncio.create_task(manager.broadcast(message))

# Set progress callback
ingestion_pipeline.set_progress_callback(progress_callback)

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Milvus connection
        milvus_stats = milvus_indexer.get_collection_stats()
        
        # Check storage connection
        storage_docs = len(storage.list_documents())
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "milvus": "connected" if milvus_stats else "disconnected",
                "storage": "connected",
                "embedding_model": "loaded"
            },
            "stats": {
                "total_documents": storage_docs,
                "vector_count": milvus_stats.get("num_entities", 0)
            },
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.post("/ingest")
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chunk_strategy: str = "token",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    metadata: Optional[str] = None
):
    """Ingest a PDF document"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Read file data
        file_data = await file.read()
        
        # Parse metadata if provided
        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        # Start ingestion in background
        task_id = str(uuid.uuid4())
        
        async def run_ingestion():
            try:
                result = await ingestion_pipeline.ingest_pdf_async(
                    file_data,
                    file.filename,
                    parsed_metadata,
                    chunk_strategy=chunk_strategy,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                
                # Broadcast completion
                await manager.broadcast({
                    "type": "complete",
                    "task_id": task_id,
                    "result": result
                })
                
            except Exception as e:
                await manager.broadcast({
                    "type": "error",
                    "task_id": task_id,
                    "error": str(e)
                })
        
        background_tasks.add_task(run_ingestion)
        
        return {
            "status": "processing",
            "task_id": task_id,
            "message": f"Started processing {file.filename}",
            "estimated_time": ingestion_pipeline.estimate_processing_time(
                len(file_data)
            )
        }
        
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Query documents with a question"""
    try:
        # Retrieve relevant chunks
        chunks = retriever.retrieve(
            query=request.question,
            top_k=request.top_k,
            filters=request.filters,
            use_reranker=request.use_reranker
        )
        
        if not chunks:
            return QueryResponse(
                answer="Bu sorunun cevab1 verilen dokümanlarda bulunmuyor.",
                sources=[],
                metadata={"chunks_found": 0}
            )
        
        # Generate answer
        response = llm_generator.generate_answer(
            question=request.question,
            context_chunks=chunks,
            include_sources=True
        )
        
        return QueryResponse(
            answer=response["answer"],
            sources=response["sources"],
            metadata=response["metadata"]
        )
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query/stream")
async def query_documents_stream(request: QueryRequest):
    """Stream query response"""
    try:
        # Retrieve relevant chunks
        chunks = retriever.retrieve(
            query=request.question,
            top_k=request.top_k,
            filters=request.filters,
            use_reranker=request.use_reranker
        )
        
        if not chunks:
            async def error_stream():
                yield "Bu sorunun cevab1 verilen dokümanlarda bulunmuyor."
            
            return StreamingResponse(
                error_stream(),
                media_type="text/plain"
            )
        
        # Generate streaming response
        def stream_response():
            for chunk in llm_generator.generate_streaming(
                request.question,
                chunks
            ):
                yield chunk
        
        return StreamingResponse(
            stream_response(),
            media_type="text/plain"
        )
        
    except Exception as e:
        logger.error(f"Streaming query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents", response_model=DocumentResponse)
async def list_documents(
    page: int = 1,
    limit: int = 20,
    sort: str = "date"
):
    """List all documents"""
    try:
        documents = storage.list_documents()
        
        # Sort documents
        if sort == "date":
            documents.sort(key=lambda x: x["last_modified"], reverse=True)
        elif sort == "name":
            documents.sort(key=lambda x: x["metadata"].get("original_filename", ""))
        elif sort == "size":
            documents.sort(key=lambda x: x["size"], reverse=True)
        
        # Paginate
        total = len(documents)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_docs = documents[start_idx:end_idx]
        
        return DocumentResponse(
            documents=paginated_docs,
            total=total,
            page=page,
            pages=(total + limit - 1) // limit
        )
        
    except Exception as e:
        logger.error(f"Document listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get document details"""
    try:
        # Get chunks for document
        chunks = storage.get_document_chunks(document_id)
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Compile document info
        total_tokens = sum(chunk.get("token_count", 0) for chunk in chunks)
        total_chars = sum(chunk.get("char_count", 0) for chunk in chunks)
        
        return {
            "document_id": document_id,
            "chunk_count": len(chunks),
            "total_tokens": total_tokens,
            "total_characters": total_chars,
            "chunks": chunks[:5]  # Return first 5 chunks as preview
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks"""
    try:
        # Delete from storage
        storage_success = storage.delete_document(document_id)
        
        # Delete from vector database
        index_success = milvus_indexer.delete_by_document(document_id)
        
        if storage_success and index_success:
            return {
                "status": "success",
                "message": f"Document {document_id} deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete document completely"
            )
            
    except Exception as e:
        logger.error(f"Document deletion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/{document_id}/reindex")
async def reindex_document(
    document_id: str,
    chunk_strategy: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None
):
    """Reindex document with different parameters"""
    try:
        result = ingestion_pipeline.reindex_document(
            document_id,
            chunk_strategy,
            chunk_size,
            chunk_overlap
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/{document_id}/summarize")
async def summarize_document(document_id: str):
    """Generate document summary"""
    try:
        chunks = storage.get_document_chunks(document_id)
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found")
        
        summary = llm_generator.summarize_document(chunks)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summarization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_system_stats():
    """Get system statistics"""
    try:
        documents = storage.list_documents()
        milvus_stats = milvus_indexer.get_collection_stats()
        
        total_size = sum(doc["size"] for doc in documents)
        
        return {
            "documents": {
                "total": len(documents),
                "total_size_mb": total_size / (1024 * 1024),
            },
            "vectors": {
                "total_chunks": milvus_stats.get("num_entities", 0),
                "collection_loaded": milvus_stats.get("is_loaded", False)
            },
            "system": {
                "embedding_model": settings.EMBEDDING_MODEL,
                "reranker_model": settings.RERANKER_MODEL,
                "llm_provider": settings.LLM_PROVIDER
            }
        }
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            # Echo received message (optional)
            await websocket.send_json({"type": "echo", "message": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )