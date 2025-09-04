import io
import json
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from minio import Minio
from minio.error import S3Error
from app.config import settings

logger = logging.getLogger(__name__)


class MinIOStorage:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self._ensure_buckets()
    
    def _ensure_buckets(self):
        """Create buckets if they don't exist"""
        buckets = [settings.MINIO_BUCKET_DOCS, settings.MINIO_BUCKET_CHUNKS]
        
        for bucket in buckets:
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    logger.info(f"Created bucket: {bucket}")
                else:
                    logger.info(f"Bucket already exists: {bucket}")
            except S3Error as e:
                logger.error(f"Error creating bucket {bucket}: {e}")
                raise
    
    def upload_pdf(self, file_data: bytes, filename: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Upload PDF to MinIO
        
        Args:
            file_data: PDF file bytes
            filename: Original filename
            metadata: Optional metadata dictionary
        
        Returns:
            document_id: Unique identifier for the document
        """
        # Generate document ID
        doc_hash = hashlib.md5(file_data).hexdigest()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        document_id = f"doc_{doc_hash[:8]}_{timestamp}"
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "original_filename": filename,
            "document_id": document_id,
            "upload_timestamp": datetime.now().isoformat(),
            "file_size": str(len(file_data))
        })
        
        # Upload to MinIO
        try:
            object_name = f"{document_id}/{filename}"
            self.client.put_object(
                settings.MINIO_BUCKET_DOCS,
                object_name,
                io.BytesIO(file_data),
                len(file_data),
                content_type="application/pdf",
                metadata=metadata
            )
            logger.info(f"Uploaded PDF: {object_name}")
            return document_id
        except S3Error as e:
            logger.error(f"Error uploading PDF: {e}")
            raise
    
    def download_pdf(self, document_id: str, filename: str) -> bytes:
        """
        Download PDF from MinIO
        
        Args:
            document_id: Document identifier
            filename: Original filename
        
        Returns:
            PDF file bytes
        """
        try:
            object_name = f"{document_id}/{filename}"
            response = self.client.get_object(
                settings.MINIO_BUCKET_DOCS,
                object_name
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error(f"Error downloading PDF: {e}")
            raise
    
    def save_chunk(self, document_id: str, chunk_id: str, chunk_data: Dict[str, Any]) -> bool:
        """
        Save text chunk to MinIO
        
        Args:
            document_id: Document identifier
            chunk_id: Unique chunk identifier
            chunk_data: Dictionary containing chunk text and metadata
        
        Returns:
            Success status
        """
        try:
            object_name = f"{document_id}/{chunk_id}.json"
            data = json.dumps(chunk_data, ensure_ascii=False).encode('utf-8')
            
            self.client.put_object(
                settings.MINIO_BUCKET_CHUNKS,
                object_name,
                io.BytesIO(data),
                len(data),
                content_type="application/json"
            )
            logger.debug(f"Saved chunk: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Error saving chunk: {e}")
            return False
    
    def get_chunk(self, document_id: str, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve chunk from MinIO
        
        Args:
            document_id: Document identifier
            chunk_id: Chunk identifier
        
        Returns:
            Chunk data dictionary or None if not found
        """
        try:
            object_name = f"{document_id}/{chunk_id}.json"
            response = self.client.get_object(
                settings.MINIO_BUCKET_CHUNKS,
                object_name
            )
            data = response.read()
            response.close()
            response.release_conn()
            
            return json.loads(data.decode('utf-8'))
        except S3Error as e:
            logger.error(f"Error retrieving chunk: {e}")
            return None
    
    def save_chunks_batch(self, document_id: str, chunks: List[Dict[str, Any]]) -> int:
        """
        Save multiple chunks in batch
        
        Args:
            document_id: Document identifier
            chunks: List of chunk dictionaries with 'chunk_id' field
        
        Returns:
            Number of successfully saved chunks
        """
        saved_count = 0
        for chunk in chunks:
            chunk_id = chunk.get('chunk_id')
            if chunk_id and self.save_chunk(document_id, chunk_id, chunk):
                saved_count += 1
        
        logger.info(f"Saved {saved_count}/{len(chunks)} chunks for document {document_id}")
        return saved_count
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all documents in storage
        
        Returns:
            List of document metadata
        """
        documents = []
        try:
            objects = self.client.list_objects(
                settings.MINIO_BUCKET_DOCS,
                recursive=False
            )
            
            seen_docs = set()
            for obj in objects:
                # Extract document_id from path
                doc_id = obj.object_name.split('/')[0]
                if doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    
                    # Try to get metadata
                    stat = self.client.stat_object(
                        settings.MINIO_BUCKET_DOCS,
                        obj.object_name
                    )
                    
                    documents.append({
                        "document_id": doc_id,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat(),
                        "metadata": stat.metadata
                    })
            
            return documents
        except S3Error as e:
            logger.error(f"Error listing documents: {e}")
            return []
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete document and all its chunks
        
        Args:
            document_id: Document identifier
        
        Returns:
            Success status
        """
        try:
            # Delete from docs bucket
            doc_objects = self.client.list_objects(
                settings.MINIO_BUCKET_DOCS,
                prefix=f"{document_id}/",
                recursive=True
            )
            
            for obj in doc_objects:
                self.client.remove_object(
                    settings.MINIO_BUCKET_DOCS,
                    obj.object_name
                )
            
            # Delete from chunks bucket
            chunk_objects = self.client.list_objects(
                settings.MINIO_BUCKET_CHUNKS,
                prefix=f"{document_id}/",
                recursive=True
            )
            
            for obj in chunk_objects:
                self.client.remove_object(
                    settings.MINIO_BUCKET_CHUNKS,
                    obj.object_name
                )
            
            logger.info(f"Deleted document and chunks: {document_id}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting document: {e}")
            return False
    
    def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a document
        
        Args:
            document_id: Document identifier
        
        Returns:
            List of chunk data dictionaries
        """
        chunks = []
        try:
            objects = self.client.list_objects(
                settings.MINIO_BUCKET_CHUNKS,
                prefix=f"{document_id}/",
                recursive=True
            )
            
            for obj in objects:
                chunk_data = self.get_chunk(
                    document_id, 
                    obj.object_name.split('/')[-1].replace('.json', '')
                )
                if chunk_data:
                    chunks.append(chunk_data)
            
            # Sort by chunk index if available
            chunks.sort(key=lambda x: x.get('chunk_index', 0))
            return chunks
        except S3Error as e:
            logger.error(f"Error getting document chunks: {e}")
            return []


# Singleton instance
storage = MinIOStorage()