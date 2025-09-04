import logging
import asyncio
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime
import traceback

from app.storage import storage
from app.parse import pdf_parser
from app.chunk import default_chunker, HybridChunker
from app.embed import embedding_generator
from app.index import milvus_indexer

logger = logging.getLogger(__name__)


@dataclass
class IngestionProgress:
    """Progress tracking for ingestion"""
    stage: str
    progress: float
    message: str
    current_step: int
    total_steps: int
    document_id: Optional[str] = None
    error: Optional[str] = None


class IngestionPipeline:
    def __init__(self):
        self.storage = storage
        self.parser = pdf_parser
        self.chunker = default_chunker
        self.embedder = embedding_generator
        self.indexer = milvus_indexer
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[IngestionProgress], None]] = None
        self.current_progress = IngestionProgress("idle", 0.0, "Ready", 0, 0)
    
    def set_progress_callback(self, callback: Callable[[IngestionProgress], None]):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def _update_progress(self, stage: str, progress: float, message: str, current_step: int = 0, total_steps: int = 0, error: Optional[str] = None):
        """Update progress and call callback if set"""
        self.current_progress = IngestionProgress(
            stage=stage,
            progress=progress,
            message=message,
            current_step=current_step,
            total_steps=total_steps,
            document_id=self.current_progress.document_id,
            error=error
        )
        
        if self.progress_callback:
            self.progress_callback(self.current_progress)
        
        logger.info(f"[{stage}] {progress:.1f}% - {message}")
    
    def ingest_pdf(
        self,
        file_data: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_strategy: str = "token",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> Dict[str, Any]:
        """
        Main ingestion pipeline for PDF files
        
        Args:
            file_data: PDF file bytes
            filename: Original filename
            metadata: Optional metadata
            chunk_strategy: Chunking strategy ("token", "semantic", "hybrid")
            chunk_size: Target chunk size
            chunk_overlap: Chunk overlap
        
        Returns:
            Ingestion results with metrics
        """
        start_time = datetime.now()
        document_id = None
        
        try:
            # Stage 1: Upload PDF to storage
            self._update_progress("upload", 5.0, "Uploading PDF to storage", 1, 6)
            document_id = self.storage.upload_pdf(file_data, filename, metadata)
            self.current_progress.document_id = document_id
            
            # Stage 2: Parse PDF
            self._update_progress("parsing", 15.0, "Extracting text from PDF", 2, 6)
            pages, doc_metadata = self.parser.extract_text_from_pdf(file_data)
            
            if not pages:
                raise ValueError("No text content found in PDF")
            
            # Stage 3: Chunk text
            self._update_progress("chunking", 30.0, f"Creating text chunks ({chunk_strategy})", 3, 6)
            
            # Select chunker based on strategy
            if chunk_strategy == "hybrid":
                chunker = HybridChunker(chunk_size, chunk_overlap)
                chunks = chunker.chunk_text(
                    "\\n\\n".join(page.text for page in pages),
                    document_id,
                    metadata
                )
            else:
                from app.chunk import TextChunker
                chunker = TextChunker(chunk_size, chunk_overlap, chunk_strategy)
                chunks = chunker.chunk_pages(pages, document_id, preserve_pages=True)
            
            if not chunks:
                raise ValueError("No chunks created from text")
            
            # Stage 4: Generate embeddings
            self._update_progress("embedding", 50.0, f"Generating embeddings for {len(chunks)} chunks", 4, 6)
            
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = self.embedder.generate_embeddings_batch(chunk_texts, show_progress=False)
            
            # Stage 5: Save chunks to storage
            self._update_progress("storing", 70.0, "Saving chunks to storage", 5, 6)
            
            # Prepare chunk data for storage
            chunk_data_list = []
            for chunk in chunks:
                chunk_dict = {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                    "token_count": chunk.token_count,
                    "char_count": chunk.char_count
                }
                chunk_data_list.append(chunk_dict)
            
            saved_count = self.storage.save_chunks_batch(document_id, chunk_data_list)
            
            # Stage 6: Index in vector database
            self._update_progress("indexing", 85.0, "Indexing chunks in vector database", 6, 6)
            
            # Prepare data for Milvus
            milvus_chunks = []
            for chunk in chunks:
                milvus_chunk = {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "metadata": chunk.metadata
                }
                milvus_chunks.append(milvus_chunk)
            
            indexed_count = self.indexer.insert_chunks(milvus_chunks, embeddings)
            
            # Complete
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            self._update_progress("complete", 100.0, f"Processing complete: {len(chunks)} chunks indexed", 6, 6)
            
            # Compile results
            results = {
                "status": "success",
                "document_id": document_id,
                "processing_time": processing_time,
                "stats": {
                    "pages_processed": len(pages),
                    "chunks_created": len(chunks),
                    "chunks_saved": saved_count,
                    "chunks_indexed": indexed_count,
                    "total_tokens": sum(chunk.token_count for chunk in chunks),
                    "avg_chunk_size": sum(chunk.token_count for chunk in chunks) / len(chunks) if chunks else 0
                },
                "document_metadata": {
                    "title": doc_metadata.title,
                    "author": doc_metadata.author,
                    "page_count": doc_metadata.page_count,
                    "file_size": doc_metadata.file_size,
                    "creation_date": doc_metadata.creation_date
                },
                "chunk_strategy": chunk_strategy,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }
            
            logger.info(f"Successfully ingested document {document_id} in {processing_time:.2f}s")
            return results
            
        except Exception as e:
            error_msg = f"Ingestion failed: {str(e)}"
            logger.error(f"{error_msg}\\n{traceback.format_exc()}")
            
            # Cleanup on error
            if document_id:
                try:
                    self._cleanup_failed_ingestion(document_id)
                except Exception as cleanup_error:
                    logger.error(f"Cleanup failed: {cleanup_error}")
            
            self._update_progress("error", 0.0, error_msg, 0, 0, error=error_msg)
            
            return {
                "status": "error",
                "document_id": document_id,
                "error": error_msg,
                "processing_time": (datetime.now() - start_time).total_seconds()
            }
    
    def _cleanup_failed_ingestion(self, document_id: str):
        """Cleanup resources for failed ingestion"""
        logger.info(f"Cleaning up failed ingestion for document {document_id}")
        
        # Remove from storage
        self.storage.delete_document(document_id)
        
        # Remove from vector database
        self.indexer.delete_by_document(document_id)
    
    async def ingest_pdf_async(
        self,
        file_data: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Async version of PDF ingestion"""
        # Run in thread pool since most operations are CPU-bound
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.ingest_pdf,
            file_data,
            filename,
            metadata,
            kwargs.get("chunk_strategy", "token"),
            kwargs.get("chunk_size", 512),
            kwargs.get("chunk_overlap", 50)
        )
    
    def batch_ingest(
        self,
        files: List[Dict[str, Any]],
        **common_params
    ) -> List[Dict[str, Any]]:
        """
        Batch ingest multiple files
        
        Args:
            files: List of file dictionaries with 'data', 'filename', 'metadata'
            common_params: Common parameters for all files
        
        Returns:
            List of ingestion results
        """
        results = []
        total_files = len(files)
        
        for i, file_info in enumerate(files):
            try:
                self._update_progress(
                    "batch_processing",
                    (i / total_files) * 100,
                    f"Processing file {i+1} of {total_files}: {file_info['filename']}",
                    i + 1,
                    total_files
                )
                
                result = self.ingest_pdf(
                    file_info["data"],
                    file_info["filename"],
                    file_info.get("metadata"),
                    **common_params
                )
                
                results.append(result)
                
            except Exception as e:
                error_result = {
                    "status": "error",
                    "filename": file_info["filename"],
                    "error": str(e)
                }
                results.append(error_result)
                logger.error(f"Error processing {file_info['filename']}: {e}")
        
        return results
    
    def reindex_document(
        self,
        document_id: str,
        new_chunk_strategy: Optional[str] = None,
        new_chunk_size: Optional[int] = None,
        new_chunk_overlap: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Reindex an existing document with different parameters
        
        Args:
            document_id: Document to reindex
            new_chunk_strategy: New chunking strategy
            new_chunk_size: New chunk size
            new_chunk_overlap: New chunk overlap
        
        Returns:
            Reindexing results
        """
        try:
            # Get original PDF from storage
            documents = self.storage.list_documents()
            target_doc = None
            
            for doc in documents:
                if doc["document_id"] == document_id:
                    target_doc = doc
                    break
            
            if not target_doc:
                raise ValueError(f"Document {document_id} not found")
            
            # Get original filename from metadata
            filename = target_doc["metadata"].get("original_filename", "unknown.pdf")
            
            # Download PDF data
            pdf_data = self.storage.download_pdf(document_id, filename)
            
            # Remove old data
            self._cleanup_failed_ingestion(document_id)
            
            # Re-ingest with new parameters
            return self.ingest_pdf(
                pdf_data,
                filename,
                target_doc["metadata"],
                new_chunk_strategy or "token",
                new_chunk_size or 512,
                new_chunk_overlap or 50
            )
            
        except Exception as e:
            error_msg = f"Reindexing failed: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "document_id": document_id,
                "error": error_msg
            }
    
    def get_ingestion_status(self) -> IngestionProgress:
        """Get current ingestion status"""
        return self.current_progress
    
    def estimate_processing_time(
        self,
        file_size: int,
        page_count: Optional[int] = None
    ) -> float:
        """
        Estimate processing time based on file characteristics
        
        Args:
            file_size: File size in bytes
            page_count: Number of pages (if known)
        
        Returns:
            Estimated time in seconds
        """
        # Simple heuristic based on file size
        # Adjust based on your system performance
        base_time = 10  # Base processing time
        size_factor = file_size / (1024 * 1024)  # MB
        page_factor = (page_count or (file_size / 50000)) * 0.5  # Rough estimate
        
        return base_time + size_factor * 2 + page_factor


# Singleton instance
ingestion_pipeline = IngestionPipeline()