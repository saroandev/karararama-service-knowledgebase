#!/usr/bin/env python3
"""
Production RAG Server with Persistent Storage
"""
import logging
import json
import asyncio
import hashlib
import datetime
import time
from typing import List, Dict, Any, Optional
from io import BytesIO
from functools import wraps
import os

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import app modules
from app.config import settings
from app.storage import storage
# Note: EmbeddingGenerator import removed to avoid TensorFlow issues
# We'll use OpenAI embeddings directly in production

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom JSON encoder for proper UTF-8 handling
import json as builtin_json

class CustomJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return builtin_json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":")
        ).encode("utf-8")

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Pydantic models
class IngestResponse(BaseModel):
    success: bool
    document_id: str
    document_title: str
    chunks_created: int
    processing_time: float
    file_hash: str
    message: str

class QueryRequest(BaseModel):
    question: str = Field(..., description="Question to ask")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of results")
    document_id: Optional[str] = Field(default=None, description="Search in specific document")

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    processing_time: float
    model_used: str

class DocumentInfo(BaseModel):
    document_id: str
    title: str
    chunks_count: int
    created_at: str
    file_hash: str

# Global imports (to avoid repeated imports)
import sys
sys.path.append('.')

# Storage service is imported from app.storage
storage_service = storage

# Connection management for Milvus
class MilvusConnectionManager:
    """Singleton pattern for Milvus connection management"""
    _instance = None
    _connection = None
    _collection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        from pymilvus import connections
        if not connections.has_connection('default'):
            connections.connect(
                'default',
                host=settings.MILVUS_HOST,
                port=str(settings.MILVUS_PORT)
            )
        return connections
    
    def get_collection(self):
        from pymilvus import Collection
        if self._collection is None:
            self.get_connection()
            self._collection = Collection(settings.MILVUS_COLLECTION)
            # Ensure collection is loaded
            self._collection.load()
        return self._collection

milvus_manager = MilvusConnectionManager()

# Retry decorator for API calls
def retry_with_backoff(max_retries=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
            return None
        return wrapper
    return decorator

# Get embedding dimension based on model
def get_embedding_dimension():
    """Get embedding dimension based on configured model"""
    # We're using 384 dimensions to match the existing collection
    # text-embedding-3-small supports custom dimensions
    return 384

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test connections
        collection = milvus_manager.get_collection()
        entity_count = collection.num_entities
        
        # Test MinIO
        minio_status = "connected" if storage_service.client.bucket_exists(settings.MINIO_BUCKET_DOCS) else "error"
        
        return {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "services": {
                "milvus": "connected",
                "minio": minio_status,
                "collection": settings.MILVUS_COLLECTION,
                "entities": entity_count,
                "embedding_model": settings.EMBEDDING_MODEL,
                "embedding_dimension": get_embedding_dimension()
            },
            "version": "2.0.0"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@app.post("/ingest", response_model=IngestResponse)
@retry_with_backoff(max_retries=3)
async def ingest_document(file: UploadFile = File(...)):
    """
    Production PDF ingest endpoint with persistent storage
    """
    start_time = datetime.datetime.now()
    
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        logger.info(f"Starting ingest for: {file.filename}")
        
        # Read PDF data
        pdf_data = await file.read()
        file_hash = hashlib.md5(pdf_data).hexdigest()
        
        # Generate document ID
        document_id = f"doc_{file_hash[:16]}"
        
        logger.info(f"Document ID: {document_id}, Hash: {file_hash}")
        
        # Upload PDF to MinIO
        try:
            minio_doc_id = storage_service.upload_pdf(
                file_data=pdf_data,
                filename=file.filename,
                metadata={"document_id": document_id, "file_hash": file_hash}
            )
            logger.info(f"PDF uploaded to MinIO: {minio_doc_id}")
        except Exception as e:
            logger.error(f"MinIO upload failed: {e}")
            # Continue without MinIO if it fails
        
        # 1. PDF Parse
        from app.parse import PDFParser
        parser = PDFParser()
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        document_title = metadata.title or file.filename.replace('.pdf', '')
        logger.info(f"Parsed {len(pages)} pages, title: {document_title}")
        
        # 2. Text chunking (simple approach to avoid sentence-transformers)
        chunks = []
        for i, page in enumerate(pages):
            text = page.text.strip()
            if len(text) > 100:  # Skip very short pages
                # Simple chunk creation
                from dataclasses import dataclass
                
                @dataclass
                class SimpleChunk:
                    chunk_id: str
                    text: str
                    page_number: int
                
                chunk_id = f"chunk_{document_id}_{i:04d}_{hash(text[:100]) & 0xffff:04x}"
                chunk = SimpleChunk(
                    chunk_id=chunk_id,
                    text=text,
                    page_number=page.page_number
                )
                chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # 3. Connect to production Milvus
        collection = milvus_manager.get_collection()
        
        # Check if document already exists
        search_existing = collection.query(
            expr=f'document_id == "{document_id}"',
            output_fields=['id'],
            limit=1
        )
        
        if search_existing:
            return IngestResponse(
                success=False,
                document_id=document_id,
                document_title=document_title,
                chunks_created=0,
                processing_time=0,
                file_hash=file_hash,
                message="Document already exists in database"
            )
        
        # 4. Generate embeddings with batch processing
        chunk_ids = []
        document_ids = []
        document_titles = []
        texts = []
        embeddings = []
        page_nums = []
        chunk_indices = []
        created_ats = []
        file_hashes = []
        
        current_time = datetime.datetime.now().isoformat()
        
        logger.info("Generating embeddings with batch processing...")
        
        # Initialize embedding service based on provider
        if settings.LLM_PROVIDER == 'openai':
            from openai import OpenAI
            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Process in batches for OpenAI
            batch_size = 20  # OpenAI recommended batch size
            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                batch_chunks = chunks[batch_start:batch_end]
                batch_texts = [chunk.text for chunk in batch_chunks]
                
                # Generate embeddings for batch
                try:
                    response = openai_client.embeddings.create(
                        model='text-embedding-3-small',
                        input=batch_texts
                    )
                    # Truncate embeddings to 384 dimensions to match collection
                    batch_embeddings = [data.embedding[:384] for data in response.data]
                except Exception as e:
                    logger.error(f"OpenAI embedding generation failed: {e}")
                    raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")
                
                # Collect batch data
                for i, (chunk, embedding) in enumerate(zip(batch_chunks, batch_embeddings)):
                    idx = batch_start + i
                    chunk_ids.append(chunk.chunk_id)
                    document_ids.append(document_id)
                    document_titles.append(document_title)
                    texts.append(chunk.text)
                    embeddings.append(embedding)
                    page_nums.append(chunk.page_number)
                    chunk_indices.append(idx)
                    created_ats.append(current_time)
                    file_hashes.append(file_hash)
                
                logger.info(f"Processed {batch_end}/{len(chunks)} chunks")
        else:
            # Fallback to OpenAI if local model provider is not OpenAI
            logger.warning("Local embedding models require TensorFlow. Falling back to OpenAI.")
            from openai import OpenAI
            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Process in batches for OpenAI
            batch_size = 20
            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                batch_chunks = chunks[batch_start:batch_end]
                batch_texts = [chunk.text for chunk in batch_chunks]
                
                try:
                    response = openai_client.embeddings.create(
                        model='text-embedding-3-small',
                        input=batch_texts
                    )
                    # Truncate embeddings to 384 dimensions to match collection
                    batch_embeddings = [data.embedding[:384] for data in response.data]
                except Exception as e:
                    logger.error(f"OpenAI embedding generation failed: {e}")
                    raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")
                
                for i, (chunk, embedding) in enumerate(zip(batch_chunks, batch_embeddings)):
                    idx = batch_start + i
                    chunk_ids.append(chunk.chunk_id)
                    document_ids.append(document_id)
                    document_titles.append(document_title)
                    texts.append(chunk.text)
                    embeddings.append(embedding)
                    page_nums.append(chunk.page_number)
                    chunk_indices.append(idx)
                    created_ats.append(current_time)
                    file_hashes.append(file_hash)
                
                logger.info(f"Processed {batch_end}/{len(chunks)} chunks")
        
        # Save chunks to MinIO
        try:
            for i, (chunk_id, text) in enumerate(zip(chunk_ids, texts)):
                storage_service.upload_chunk(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    chunk_text=text,
                    metadata={
                        "page_num": page_nums[i],
                        "chunk_index": chunk_indices[i]
                    }
                )
            logger.info(f"Saved {len(chunk_ids)} chunks to MinIO")
        except Exception as e:
            logger.error(f"Failed to save chunks to MinIO: {e}")
            # Continue without MinIO storage
        
        # 5. Insert to Milvus (PERSISTENT)
        logger.info("Inserting to production Milvus...")
        
        # Prepare minio_object_paths
        minio_object_paths = [f"{document_id}/{chunk_id}.json" for chunk_id in chunk_ids]
        
        # Prepare metadata as JSON strings
        metadata_list = []
        for i in range(len(chunk_ids)):
            meta = {
                "document_title": document_titles[i],
                "file_hash": file_hashes[i]
            }
            metadata_list.append(json.dumps(meta))
        
        # Generate unique IDs for chunks
        ids = [f"{document_id}_{i:04d}" for i in range(len(chunk_ids))]
        
        # Text data is already prepared in the texts list from embedding generation
        # No need to re-extract from chunks
        
        # Combine all metadata into single field for each chunk
        combined_metadata = []
        for i in range(len(chunks)):
            meta = {
                "chunk_id": chunk_ids[i],
                "page_number": page_nums[i],
                "minio_object_path": minio_object_paths[i],
                "document_title": document_titles[i],
                "file_hash": file_hashes[i],
                "created_at": int(datetime.datetime.now().timestamp() * 1000)
            }
            combined_metadata.append(meta)
        
        # Data order must match schema: id, document_id, chunk_index, text, embedding, metadata
        data = [
            ids,                 # id field (VARCHAR)
            document_ids,        # document_id field
            chunk_indices,       # chunk_index field
            texts,              # text field
            embeddings,          # embedding field
            combined_metadata    # metadata field (as dict, not JSON string)
        ]
        
        insert_result = collection.insert(data)
        collection.load()  # Reload for immediate search
        
        processing_time = (datetime.datetime.now() - start_time).total_seconds()
        
        logger.info(f"Successfully ingested {len(chunks)} chunks in {processing_time:.2f}s")
        
        return IngestResponse(
            success=True,
            document_id=document_id,
            document_title=document_title,
            chunks_created=len(chunks),
            processing_time=processing_time,
            file_hash=file_hash,
            message=f"Document successfully ingested with {len(chunks)} chunks"
        )
        
    except Exception as e:
        logger.error(f"Ingest error: {str(e)}")
        processing_time = (datetime.datetime.now() - start_time).total_seconds()
        
        return IngestResponse(
            success=False,
            document_id="",
            document_title="",
            chunks_created=0,
            processing_time=processing_time,
            file_hash="",
            message=f"Ingest failed: {str(e)}"
        )

@app.post("/query", response_model=QueryResponse)
@retry_with_backoff(max_retries=3)
async def query_documents(request: QueryRequest):
    """
    Production query endpoint with persistent storage
    """
    start_time = datetime.datetime.now()
    
    try:
        logger.info(f"Query: {request.question}")
        
        # Connect to Milvus
        collection = milvus_manager.get_collection()
        
        # Generate query embedding based on provider
        if settings.LLM_PROVIDER == 'openai':
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            query_response = client.embeddings.create(
                model='text-embedding-3-small',
                input=request.question
            )
            # Truncate embedding to 384 dimensions to match collection
            query_embedding = query_response.data[0].embedding[:384]
        else:
            # Fallback to OpenAI for embeddings
            logger.warning("Local embedding models require TensorFlow. Using OpenAI.")
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            query_response = client.embeddings.create(
                model='text-embedding-3-small',
                input=request.question
            )
            # Truncate embedding to 384 dimensions to match collection
            query_embedding = query_response.data[0].embedding[:384]
        
        # Prepare search expression (filters)
        expr = None
        if request.document_id:
            expr = f'document_id == "{request.document_id}"'
        
        # Vector search
        search_results = collection.search(
            [query_embedding],
            'embedding',
            {'metric_type': 'IP'},  # Inner Product metric
            limit=request.top_k,
            expr=expr,
            output_fields=['document_id', 'chunk_index', 'text', 'metadata']
        )
        
        if not search_results[0]:
            return QueryResponse(
                answer="İlgili bilgi bulunamadı.",
                sources=[],
                processing_time=0,
                model_used="gpt-4o-mini"
            )
        
        # Prepare context
        sources = []
        context_parts = []
        
        for i, result in enumerate(search_results[0]):
            score = result.score
            # Access entity fields directly as attributes
            doc_id = result.entity.document_id
            chunk_index = result.entity.chunk_index if hasattr(result.entity, 'chunk_index') else 0
            text = result.entity.text if hasattr(result.entity, 'text') else ''
            metadata = result.entity.metadata if hasattr(result.entity, 'metadata') else {}
            
            # Parse metadata (now it's a dict, not JSON string)
            if isinstance(metadata, str):
                meta_dict = json.loads(metadata)
            else:
                meta_dict = metadata if metadata else {}
            
            doc_title = meta_dict.get('document_title', 'Unknown')
            chunk_id = meta_dict.get('chunk_id', f'chunk_{chunk_index}')
            page_num = meta_dict.get('page_number', 0)
            created_at = meta_dict.get('created_at', 0)
            
            sources.append({
                "rank": i + 1,
                "score": round(score, 3),
                "document_id": doc_id,
                "document_title": doc_title,
                "page_number": page_num,
                "text_preview": text[:200] + "..." if len(text) > 200 else text,
                "created_at": created_at
            })
            
            context_parts.append(f"[Kaynak {i+1} - Sayfa {page_num}]: {text}")
        
        # Generate answer
        context = "\n\n".join(context_parts)
        
        # Generate answer based on provider
        if settings.LLM_PROVIDER == 'openai':
            from openai import OpenAI
            if 'client' not in locals():
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            chat_response = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                messages=[
                {
                    "role": "system", 
                    "content": """Sen yardımsever bir RAG (Retrieval-Augmented Generation) asistanısın.

GÖREVİN:
• Verilen kaynak belgelerden faydalanarak soruları net ve anlaşılır şekilde cevaplamak
• Cevaplarını Türkçe dilbilgisi kurallarına uygun, akıcı bir dille yazmak
• Her zaman kaynak numaralarını belirtmek (Örn: [Kaynak 1], [Kaynak 2-3])

CEVAP FORMATI:
1. Soruya doğrudan ve özlü bir cevap ver
2. Gerekirse madde madde veya paragraflar halinde açıkla
3. Her bilgi için hangi kaynaktan alındığını belirt
4. Eğer sorunun cevabı kaynak belgelerde yoksa, "Sağlanan kaynaklarda bu soruya ilişkin bilgi bulunmamaktadır" de

ÖNEMLI:
• Sadece verilen kaynaklardaki bilgileri kullan
• Kendi bilgini ekleme, sadece kaynakları yorumla
• Belirsizlik varsa bunu belirt"""
                },
                {
                    "role": "user",
                    "content": f"""Kaynak Belgeler:
{context}

Soru: {request.question}

Lütfen bu soruya kaynak belgelere dayanarak cevap ver ve hangi kaynak(lardan) bilgi aldığını belirt."""
                }
            ],
                max_tokens=500
            )
            
            answer = chat_response.choices[0].message.content
            model_used = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        else:
            # Use Ollama or other local LLM
            # This would need to be implemented based on your Ollama setup
            answer = f"Based on the provided context: {context_parts[0][:200]}..."
            model_used = settings.OLLAMA_MODEL
        processing_time = (datetime.datetime.now() - start_time).total_seconds()
        
        logger.info(f"Query completed in {processing_time:.2f}s")
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            processing_time=processing_time,
            model_used=model_used
        )
        
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/documents", response_model=List[DocumentInfo])
async def list_documents():
    """
    List all ingested documents
    """
    try:
        collection = milvus_manager.get_collection()
        
        # Get unique documents
        results = collection.query(
            expr="chunk_index == 0",  # Only first chunk of each document
            output_fields=['document_id', 'metadata']
        )
        
        documents = []
        for result in results:
            doc_id = result.get('document_id')
            metadata = result.get('metadata')
            
            # Parse metadata - it's already a dict, not JSON string
            if isinstance(metadata, str):
                meta_dict = json.loads(metadata)
            else:
                meta_dict = metadata if metadata else {}
            
            doc_title = meta_dict.get('document_title', 'Unknown')
            file_hash = meta_dict.get('file_hash', '')
            created_at = meta_dict.get('created_at', 0)
            
            # Convert timestamp to ISO format if exists
            if created_at:
                # created_at is stored as milliseconds timestamp
                created_at_str = datetime.datetime.fromtimestamp(created_at / 1000).isoformat()
            else:
                created_at_str = datetime.datetime.now().isoformat()
            
            # Count chunks for this document
            chunk_count = len(collection.query(
                expr=f'document_id == "{doc_id}"',
                output_fields=['id']
            ))
            
            documents.append(DocumentInfo(
                document_id=doc_id,
                title=doc_title,
                chunks_count=chunk_count,
                created_at=created_at_str,
                file_hash=file_hash
            ))
        
        return documents
        
    except Exception as e:
        logger.error(f"List documents error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and all its chunks
    """
    try:
        collection = milvus_manager.get_collection()
        
        # Find document chunks
        chunks = collection.query(
            expr=f'document_id == "{document_id}"',
            output_fields=['id']
        )
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete chunks from Milvus
        ids_to_delete = [chunk['id'] for chunk in chunks]
        collection.delete(expr=f"id in {ids_to_delete}")
        
        # Try to delete from MinIO as well
        try:
            storage_service.delete_document(document_id)
            logger.info(f"Deleted document {document_id} from MinIO")
        except Exception as e:
            logger.warning(f"Failed to delete from MinIO: {e}")
        
        return {
            "success": True,
            "document_id": document_id,
            "deleted_chunks": len(chunks),
            "message": f"Document and {len(chunks)} chunks deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"Delete document error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "production_server:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )