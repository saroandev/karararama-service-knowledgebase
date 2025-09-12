import io
import json
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from functools import lru_cache
import time

from minio import Minio
from minio.error import S3Error
from app.config import settings

logger = logging.getLogger(__name__)


class MinIOStorage:
    def __init__(self):
        # Create MinIO client with custom HTTP client for larger files
        import urllib3
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=30.0, read=600.0),
            maxsize=50,
            retries=urllib3.Retry(
                total=5,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            http_client=http_client
        )
        self._ensure_buckets()
        
        # Initialize cache
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes TTL
        self._cache_max_size = 100  # Maximum number of cached items
    
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
        Upload PDF to MinIO with chunking workaround for Docker Desktop on macOS
        
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
        
        
        # Prepare metadata (ASCII-safe for MinIO)
        if metadata is None:
            metadata = {}
        
        # Ensure ASCII-safe filename for metadata
        safe_filename = filename.encode('ascii', 'ignore').decode('ascii')
        if not safe_filename:
            safe_filename = "document.pdf"
        
        metadata.update({
            "original_filename": safe_filename,
            "document_id": document_id,
            "upload_timestamp": datetime.now().isoformat(),
            "file_size": str(len(file_data))
        })
        
        # Use safe filename for object name to avoid encoding issues
        safe_object_name = filename.encode('ascii', 'ignore').decode('ascii')
        if not safe_object_name:
            safe_object_name = f"document_{doc_hash[:8]}.pdf"
        
        # Docker Desktop on macOS workaround: Split large files into chunks
        CHUNK_SIZE = 100 * 1024  # 100KB chunks (safe based on testing)
        file_size = len(file_data)
        
        try:
            if file_size <= CHUNK_SIZE:
                # Small file - direct upload
                object_name = f"{document_id}/{safe_object_name}"
                self.client.put_object(
                    settings.MINIO_BUCKET_DOCS,
                    object_name,
                    io.BytesIO(file_data),
                    len(file_data),
                    content_type="application/pdf",
                    metadata=metadata
                )
                logger.info(f"Uploaded small PDF directly: {object_name}")
            else:
                # Large file - split into chunks
                num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
                
                # Save metadata with chunk info
                metadata["chunked"] = "true"
                metadata["num_chunks"] = str(num_chunks)
                metadata["chunk_size"] = str(CHUNK_SIZE)
                
                # Upload metadata
                meta_object = f"{document_id}/.metadata"
                meta_data = json.dumps(metadata).encode('utf-8')
                self.client.put_object(
                    settings.MINIO_BUCKET_DOCS,
                    meta_object,
                    io.BytesIO(meta_data),
                    len(meta_data),
                    content_type="application/json"
                )
                
                # Upload chunks
                for i in range(num_chunks):
                    start = i * CHUNK_SIZE
                    end = min(start + CHUNK_SIZE, file_size)
                    chunk_data = file_data[start:end]
                    chunk_name = f"{document_id}/chunk_{i:04d}.part"
                    
                    self.client.put_object(
                        settings.MINIO_BUCKET_DOCS,
                        chunk_name,
                        io.BytesIO(chunk_data),
                        len(chunk_data),
                        content_type="application/octet-stream"
                    )
                    logger.debug(f"Uploaded chunk {i+1}/{num_chunks}: {chunk_name}")
                
                logger.info(f"Uploaded large PDF in {num_chunks} chunks: {document_id}")
            
            return document_id
        except S3Error as e:
            logger.error(f"Error uploading PDF: {e}")
            raise
    
    def download_pdf(self, document_id: str, filename: str) -> bytes:
        """
        Download PDF from MinIO (handles both direct and chunked files)
        
        Args:
            document_id: Document identifier
            filename: Original filename
        
        Returns:
            PDF file bytes
        """
        try:
            # First try to get metadata to check if file is chunked
            meta_object = f"{document_id}/.metadata"
            try:
                response = self.client.get_object(
                    settings.MINIO_BUCKET_DOCS,
                    meta_object
                )
                meta_data = response.read()
                response.close()
                response.release_conn()
                metadata = json.loads(meta_data.decode('utf-8'))
                
                if metadata.get("chunked") == "true":
                    # File is chunked - reassemble
                    num_chunks = int(metadata["num_chunks"])
                    chunks = []
                    
                    for i in range(num_chunks):
                        chunk_name = f"{document_id}/chunk_{i:04d}.part"
                        response = self.client.get_object(
                            settings.MINIO_BUCKET_DOCS,
                            chunk_name
                        )
                        chunk_data = response.read()
                        response.close()
                        response.release_conn()
                        chunks.append(chunk_data)
                    
                    logger.info(f"Downloaded and reassembled {num_chunks} chunks for {document_id}")
                    return b''.join(chunks)
            except S3Error:
                # No metadata file - try direct download
                pass
            
            # Direct download (file not chunked)
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
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get item from cache if not expired"""
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_data
            else:
                # Remove expired item
                del self._cache[cache_key]
        return None
    
    def _add_to_cache(self, cache_key: str, data: Dict[str, Any]):
        """Add item to cache with TTL"""
        # Check cache size limit
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest item
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        self._cache[cache_key] = (data, time.time())
    
    def get_chunks_batch(self, minio_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve multiple chunks from MinIO in batch with caching
        
        Args:
            minio_paths: List of MinIO object paths (bucket/path format)
        
        Returns:
            List of chunk data dictionaries
        """
        chunks = []
        uncached_paths = []
        uncached_indices = []
        
        # Check cache first
        for i, path in enumerate(minio_paths):
            cached_data = self._get_from_cache(path)
            if cached_data:
                chunks.append(cached_data)
                logger.debug(f"Cache hit for {path}")
            else:
                chunks.append(None)  # Placeholder
                uncached_paths.append(path)
                uncached_indices.append(i)
        
        # Fetch uncached items from MinIO
        for idx, path in zip(uncached_indices, uncached_paths):
            try:
                # Parse path to extract bucket and object name
                parts = path.split('/', 1)
                if len(parts) == 2:
                    bucket, object_name = parts
                    response = self.client.get_object(bucket, object_name)
                    data = response.read()
                    response.close()
                    response.release_conn()
                    chunk_data = json.loads(data.decode('utf-8'))
                    
                    # Add to cache
                    self._add_to_cache(path, chunk_data)
                    chunks[idx] = chunk_data
                    logger.debug(f"Fetched and cached {path}")
                else:
                    logger.warning(f"Invalid MinIO path format: {path}")
            except S3Error as e:
                logger.error(f"Error retrieving chunk from {path}: {e}")
        
        return chunks
    
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
    
    def save_chunks_batch(self, document_id: str, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Save multiple chunks in batch and return MinIO paths
        
        Args:
            document_id: Document identifier
            chunks: List of chunk dictionaries with 'chunk_id' field
        
        Returns:
            List of MinIO object paths for saved chunks
        """
        saved_paths = []
        for chunk in chunks:
            chunk_id = chunk.get('chunk_id')
            if chunk_id:
                object_name = f"{document_id}/{chunk_id}.json"
                if self.save_chunk(document_id, chunk_id, chunk):
                    saved_paths.append(f"{settings.MINIO_BUCKET_CHUNKS}/{object_name}")
        
        logger.info(f"Saved {len(saved_paths)}/{len(chunks)} chunks for document {document_id}")
        return saved_paths
    
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
    
    def upload_chunk(self, document_id: str, chunk_id: str, chunk_text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Upload a single chunk to MinIO
        
        Args:
            document_id: Document identifier
            chunk_id: Chunk identifier
            chunk_text: Text content of the chunk
            metadata: Optional metadata for the chunk
        
        Returns:
            True if successful, False otherwise
        """
        chunk_data = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "text": chunk_text,
            "metadata": metadata or {}
        }
        return self.save_chunk(document_id, chunk_id, chunk_data)
    
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
            
            # Delete from raw-documents bucket
            raw_objects = self.client.list_objects(
                "raw-documents",
                prefix=f"{document_id}/",
                recursive=True
            )
            
            for obj in raw_objects:
                self.client.remove_object(
                    "raw-documents",
                    obj.object_name
                )
                logger.info(f"Deleted from raw-documents: {obj.object_name}")
            
            logger.info(f"Deleted document and chunks: {document_id}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting document: {e}")
            return False
    
    def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """
        Get document metadata from MinIO
        
        Args:
            document_id: Document identifier
        
        Returns:
            Document metadata dictionary
        """
        try:
            # Try to get metadata from raw-documents bucket first
            metadata_object = f"{document_id}/{document_id}_metadata.json"
            try:
                response = self.client.get_object("raw-documents", metadata_object)
                metadata = json.loads(response.read())
                response.close()
                return metadata
            except:
                pass
            
            # Try to get from docs bucket metadata file
            meta_object = f"{document_id}/.metadata"
            try:
                response = self.client.get_object(settings.MINIO_BUCKET_DOCS, meta_object)
                metadata = json.loads(response.read())
                response.close()
                return metadata
            except:
                pass
            
            # Try to get from object metadata
            try:
                objects = self.client.list_objects(
                    settings.MINIO_BUCKET_DOCS,
                    prefix=f"{document_id}/",
                    recursive=False
                )
                for obj in objects:
                    if not obj.object_name.endswith('/'):
                        stat = self.client.stat_object(settings.MINIO_BUCKET_DOCS, obj.object_name)
                        if stat.metadata:
                            return dict(stat.metadata)
                        break
            except:
                pass
            
            # Return default metadata if nothing found
            return {
                "document_id": document_id,
                "original_filename": f"{document_id}.pdf"
            }
            
        except Exception as e:
            logger.error(f"Error getting document metadata: {e}")
            return {
                "document_id": document_id,
                "original_filename": f"{document_id}.pdf"
            }
    
    def clear_cache(self):
        """Clear the entire cache"""
        self._cache.clear()
        logger.info("Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "size": len(self._cache),
            "max_size": self._cache_max_size,
            "ttl": self._cache_ttl
        }
    
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
    
    def upload_pdf_to_raw_documents(self, document_id: str, file_data: bytes, 
                                   filename: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Upload PDF to raw-documents bucket with original filename
        
        Args:
            document_id: Document identifier (e.g., doc_xxx)
            file_data: PDF file bytes
            filename: Original filename to preserve
            metadata: Optional metadata dictionary
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure raw-documents bucket exists
            raw_bucket = "raw-documents"
            if not self.client.bucket_exists(raw_bucket):
                self.client.make_bucket(raw_bucket)
                logger.info(f"Created bucket: {raw_bucket}")
            
            # Sanitize filename for MinIO while preserving original in metadata
            import unicodedata
            import re
            import os
            
            # Convert to lowercase first
            sanitized_filename = filename.lower()
            
            # Replace Turkish characters with proper ASCII equivalents
            # More comprehensive Turkish character mapping
            replacements = {
                'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
                'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c',
                'â': 'a', 'î': 'i', 'û': 'u', 'ê': 'e', 'ô': 'o',
                'Â': 'a', 'Î': 'i', 'Û': 'u', 'Ê': 'e', 'Ô': 'o'
            }
            for tr_char, ascii_char in replacements.items():
                sanitized_filename = sanitized_filename.replace(tr_char, ascii_char)
            
            # Normalize unicode to handle any remaining special characters
            sanitized_filename = unicodedata.normalize('NFKD', sanitized_filename)
            sanitized_filename = sanitized_filename.encode('ascii', 'ignore').decode('ascii')
            
            # Get the name and extension separately
            name_part, ext = os.path.splitext(sanitized_filename)
            
            # Replace punctuation and special chars with spaces, keep numbers and letters
            name_part = re.sub(r'[^a-z0-9\s]', ' ', name_part)
            
            # Replace multiple spaces with single space
            name_part = re.sub(r'\s+', ' ', name_part)
            
            # Remove leading/trailing spaces
            name_part = name_part.strip()
            
            # Replace spaces with underscores for the filename
            name_part = name_part.replace(' ', '_')
            
            # Handle long filenames - truncate to 200 chars + extension
            MAX_NAME_LENGTH = 200
            if len(name_part) > MAX_NAME_LENGTH:
                # Keep first 195 chars and add a short hash suffix for uniqueness
                import hashlib
                hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:5]
                name_part = f"{name_part[:195]}_{hash_suffix}"
            
            # Reconstruct filename with extension
            sanitized_filename = f"{name_part}{ext}" if ext else name_part
            
            # Upload PDF with sanitized filename
            pdf_object_name = f"{document_id}/{sanitized_filename}"
            self.client.put_object(
                raw_bucket,
                pdf_object_name,
                io.BytesIO(file_data),
                len(file_data),
                content_type="application/pdf"
            )
            logger.info(f"Uploaded PDF to raw-documents: {pdf_object_name}")
            
            # Prepare and upload metadata
            if metadata is None:
                metadata = {}
            
            metadata.update({
                "document_id": document_id,
                "original_filename": filename,
                "upload_timestamp": datetime.now().isoformat(),
                "file_size": len(file_data)
            })
            
            # Save metadata as {document_id}_metadata.json
            metadata_object_name = f"{document_id}/{document_id}_metadata.json"
            metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8')
            
            self.client.put_object(
                raw_bucket,
                metadata_object_name,
                io.BytesIO(metadata_json),
                len(metadata_json),
                content_type="application/json"
            )
            logger.info(f"Uploaded metadata to raw-documents: {metadata_object_name}")
            
            return True
            
        except S3Error as e:
            logger.error(f"Error uploading to raw-documents: {e}")
            return False


# Singleton instance
storage = MinIOStorage()