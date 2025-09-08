#!/usr/bin/env python3
"""
Production RAG Server with Persistent Storage
"""
import logging
import json
import asyncio
import hashlib
import datetime
from typing import List, Dict, Any, Optional
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Production RAG API",
    description="Production-ready RAG system with persistent storage",
    version="2.0.0"
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
import os
sys.path.append('.')

# Import MinIO storage
from minio import Minio
from minio.error import S3Error

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test connections
        from pymilvus import connections, Collection
        connections.connect('default', host='localhost', port='19530')
        
        collection = Collection('rag_production_v1')
        entity_count = collection.num_entities
        
        return {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "services": {
                "milvus": "connected",
                "collection": "rag_production_v1",
                "entities": entity_count
            },
            "version": "2.0.0"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@app.post("/ingest", response_model=IngestResponse)
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
        
        # 1. Initialize MinIO client (MANDATORY)
        try:
            import urllib3
            # Create custom HTTP client with longer timeout
            http_client = urllib3.PoolManager(
                timeout=30,
                maxsize=10,
                retries=urllib3.Retry(
                    total=3,
                    backoff_factor=0.2,
                    status_forcelist=[500, 502, 503, 504]
                )
            )
            
            minio_client = Minio(
                os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
                access_key=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
                secret_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin'),
                secure=False,
                http_client=http_client
            )
            
            # Ensure buckets exist
            for bucket_name in ['raw-documents', 'chunks', 'processed-texts']:
                if not minio_client.bucket_exists(bucket_name):
                    minio_client.make_bucket(bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
            logger.info("MinIO connected successfully")
        except Exception as e:
            logger.warning(f"MinIO connection failed: {e}. Continuing without MinIO.")
            minio_client = None
        
        # 2. PDF Parse
        from app.parse import PDFParser
        parser = PDFParser()
        pages, metadata = parser.extract_text_from_pdf(pdf_data)
        
        document_title = metadata.title or file.filename.replace('.pdf', '')
        logger.info(f"Parsed {len(pages)} pages, title: {document_title}")
        
        # 3. Save original PDF to MinIO (MANDATORY)
        try:
            pdf_path = f"{document_id}/original.pdf"
            minio_client.put_object(
                bucket_name="raw-documents",
                object_name=pdf_path,
                data=BytesIO(pdf_data),
                length=len(pdf_data),
                content_type="application/pdf",
                metadata={
                    "document-id": document_id,
                    "upload-time": datetime.datetime.now().isoformat()
                }
            )
            logger.info(f"Saved original PDF to MinIO: {pdf_path}")
        except Exception as e:
            logger.error(f"Failed to save PDF to MinIO: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save PDF to MinIO: {str(e)}"
            )
        
        # 4. Save metadata to MinIO (MANDATORY)
        metadata_obj = {
            "document_id": document_id,
            "title": document_title,
            "filename": file.filename,
            "file_hash": file_hash,
            "page_count": len(pages),
            "file_size": len(pdf_data),
            "upload_time": datetime.datetime.now().isoformat(),
            "processing_status": "in_progress"
        }
        
        try:
            metadata_path = f"{document_id}/metadata.json"
            minio_client.put_object(
                bucket_name="raw-documents",
                object_name=metadata_path,
                data=BytesIO(json.dumps(metadata_obj).encode()),
                length=len(json.dumps(metadata_obj).encode()),
                content_type="application/json"
            )
            logger.info(f"Saved metadata to MinIO: {metadata_path}")
        except Exception as e:
            logger.error(f"Failed to save metadata to MinIO: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save metadata to MinIO: {str(e)}"
            )
        
        # 5. Text chunking (simple approach to avoid sentence-transformers)
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
                
                # Save chunk to MinIO (MANDATORY)
                chunk_data = {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "document_title": document_title,
                    "text": text,
                    "page_number": page.page_number,
                    "chunk_index": i,
                    "metadata": {
                        "char_count": len(text),
                        "word_count": len(text.split()),
                        "created_at": datetime.datetime.now().isoformat()
                    }
                }
                
                chunk_path = f"{document_id}/chunk_{i:04d}.json"
                minio_client.put_object(
                    bucket_name="chunks",
                    object_name=chunk_path,
                    data=BytesIO(json.dumps(chunk_data, ensure_ascii=False).encode()),
                    length=len(json.dumps(chunk_data, ensure_ascii=False).encode()),
                    content_type="application/json"
                )
        
        logger.info(f"Created {len(chunks)} chunks and saved to MinIO")
        
        # 6. Connect to production Milvus
        from pymilvus import connections, Collection
        connections.connect('default', host='localhost', port='19530')
        collection = Collection('rag_production_v1')
        
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
        
        # 7. Generate embeddings
        from openai import OpenAI
        client = OpenAI()
        
        # Prepare batch data
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
        
        logger.info("Generating embeddings...")
        for i, chunk in enumerate(chunks):
            # Generate embedding
            response = client.embeddings.create(
                model='text-embedding-3-small',
                input=chunk.text
            )
            
            # Collect data
            chunk_ids.append(chunk.chunk_id)
            document_ids.append(document_id)
            document_titles.append(document_title)
            texts.append(chunk.text)
            embeddings.append(response.data[0].embedding)
            page_nums.append(chunk.page_number)
            chunk_indices.append(i)
            created_ats.append(current_time)
            file_hashes.append(file_hash)
            
            if (i + 1) % 5 == 0:
                logger.info(f"Processed {i + 1}/{len(chunks)} chunks")
        
        # 8. Insert to Milvus (PERSISTENT)
        logger.info("Inserting to production Milvus...")
        
        data = [
            chunk_ids, document_ids, document_titles, texts,
            embeddings, page_nums, chunk_indices, created_ats, file_hashes
        ]
        
        insert_result = collection.insert(data)
        collection.load()  # Reload for immediate search
        
        # 9. Update metadata in MinIO (mark as completed)
        metadata_obj["processing_status"] = "completed"
        metadata_obj["chunks_created"] = len(chunks)
        metadata_obj["processing_time"] = (datetime.datetime.now() - start_time).total_seconds()
        
        minio_client.put_object(
            bucket_name="raw-documents",
            object_name=f"{document_id}/metadata.json",
            data=BytesIO(json.dumps(metadata_obj).encode()),
            length=len(json.dumps(metadata_obj).encode()),
            content_type="application/json"
        )
        
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
async def query_documents(request: QueryRequest):
    """
    Production query endpoint with persistent storage
    """
    start_time = datetime.datetime.now()
    
    try:
        logger.info(f"Query: {request.question}")
        
        # Connect to services
        from pymilvus import connections, Collection
        from openai import OpenAI
        
        connections.connect('default', host='localhost', port='19530')
        collection = Collection('rag_production_v1')
        client = OpenAI()
        
        # Initialize MinIO client (MANDATORY for full text retrieval)
        try:
            minio_client = Minio(
                os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
                access_key=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
                secret_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin'),
                secure=False
            )
            logger.info("MinIO connected for query processing")
        except Exception as e:
            logger.error(f"MinIO connection failed for query: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"MinIO storage is required but not available: {str(e)}"
            )
        
        # Generate query embedding
        query_response = client.embeddings.create(
            model='text-embedding-3-small',
            input=request.question
        )
        query_embedding = query_response.data[0].embedding
        
        # Prepare search expression (filters)
        expr = None
        if request.document_id:
            expr = f'document_id == "{request.document_id}"'
        
        # Vector search
        search_results = collection.search(
            [query_embedding],
            'embedding',
            {'metric_type': 'COSINE'},
            limit=request.top_k,
            expr=expr,
            output_fields=['document_id', 'document_title', 'text', 'page_num', 'created_at']
        )
        
        if not search_results[0]:
            return QueryResponse(
                answer="İlgili bilgi bulunamadı.",
                sources=[],
                processing_time=0,
                model_used="gpt-4o-mini"
            )
        
        # Prepare context and load full texts from MinIO
        sources = []
        context_parts = []
        
        for i, result in enumerate(search_results[0]):
            score = result.score
            doc_id = result.entity.get('document_id')
            doc_title = result.entity.get('document_title')
            text = result.entity.get('text')
            page_num = result.entity.get('page_num')
            created_at = result.entity.get('created_at')
            
            # Try to load full text from MinIO if available
            try:
                chunk_path = f"{doc_id}/chunk_{i:04d}.json"
                response = minio_client.get_object("chunks", chunk_path)
                chunk_data = json.loads(response.read().decode('utf-8'))
                full_text = chunk_data.get('text', text)
                response.close()
                response.release_conn()
            except Exception as e:
                logger.debug(f"Could not load chunk from MinIO: {e}, using cached text")
                full_text = text
            
            sources.append({
                "rank": i + 1,
                "score": round(score, 3),
                "document_id": doc_id,
                "document_title": doc_title,
                "page_number": page_num,
                "text_preview": full_text[:200] + "..." if len(full_text) > 200 else full_text,
                "created_at": created_at
            })
            
            context_parts.append(f"[Kaynak {i+1} - Sayfa {page_num}]: {full_text}")
        
        # Generate answer
        context = "\n\n".join(context_parts)
        
        chat_response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {
                    "role": "system", 
                    "content": """Sen bir RAG (Retrieval-Augmented Generation) asistanısın. 
                    Verilen kaynak belgelerden faydalanarak soruları cevaplıyorsun.
                    Cevabını verirken kaynak numaralarını belirt (Örn: [Kaynak 1]).
                    Eğer sorunun cevabı kaynak belgelerde yoksa, bunu açıkça belirt."""
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
        processing_time = (datetime.datetime.now() - start_time).total_seconds()
        
        logger.info(f"Query completed in {processing_time:.2f}s")
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            processing_time=processing_time,
            model_used="gpt-4o-mini"
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
        from pymilvus import connections, Collection
        
        connections.connect('default', host='localhost', port='19530')
        collection = Collection('rag_production_v1')
        
        # Get unique documents
        results = collection.query(
            expr="chunk_index == 0",  # Only first chunk of each document
            output_fields=['document_id', 'document_title', 'created_at', 'file_hash']
        )
        
        documents = []
        for result in results:
            doc_id = result.get('document_id')
            
            # Count chunks for this document
            chunk_count = len(collection.query(
                expr=f'document_id == "{doc_id}"',
                output_fields=['id']
            ))
            
            documents.append(DocumentInfo(
                document_id=doc_id,
                title=result.get('document_title'),
                chunks_count=chunk_count,
                created_at=result.get('created_at'),
                file_hash=result.get('file_hash')
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
        from pymilvus import connections, Collection
        
        connections.connect('default', host='localhost', port='19530')
        collection = Collection('rag_production_v1')
        
        # Find document chunks
        chunks = collection.query(
            expr=f'document_id == "{document_id}"',
            output_fields=['id']
        )
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete chunks
        ids_to_delete = [chunk['id'] for chunk in chunks]
        collection.delete(f"id in {ids_to_delete}")
        
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