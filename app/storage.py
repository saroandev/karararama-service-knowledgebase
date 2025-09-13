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

# Sanitize filename for MinIO while preserving original in metadata
import unicodedata
import re
import os

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
        CHUNK_SIZE = 500 * 1024  # 500KB chunks for better performance
        
        try:
            if len(file_data) > CHUNK_SIZE:
                # Upload in parts manually to work around Docker Desktop issues
                # This is a workaround for Docker Desktop on macOS file size limitations
                
                # Create a multipart upload session
                # We'll use put_object with smaller chunks
                logger.info(f"Uploading large file {safe_object_name} in chunks (size: {len(file_data)} bytes)")
                
                # Use BytesIO to create a file-like object
                file_stream = io.BytesIO(file_data)
                
                # Upload the entire file (MinIO client will handle chunking internally)
                self.client.put_object(
                    settings.MINIO_BUCKET_DOCS,
                    safe_object_name,
                    file_stream,
                    len(file_data),
                    content_type='application/pdf',
                    metadata=metadata
                )
                
                logger.info(f"Successfully uploaded {safe_object_name} to MinIO")
            else:
                # Small file - upload directly
                logger.info(f"Uploading small file {safe_object_name} (size: {len(file_data)} bytes)")
                self.client.put_object(
                    settings.MINIO_BUCKET_DOCS,
                    safe_object_name,
                    io.BytesIO(file_data),
                    len(file_data),
                    content_type='application/pdf',
                    metadata=metadata
                )
                logger.info(f"Successfully uploaded {safe_object_name} to MinIO")
            
            # Clear cache for this document
            self._invalidate_cache(document_id)
            
            return document_id
            
        except S3Error as e:
            logger.error(f"Failed to upload PDF to MinIO: {e}")
            # Try alternative approach - save to temp file first
            import tempfile
            import os
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(file_data)
                    tmp_path = tmp_file.name
                
                # Upload from file
                self.client.fput_object(
                    settings.MINIO_BUCKET_DOCS,
                    safe_object_name,
                    tmp_path,
                    content_type='application/pdf',
                    metadata=metadata
                )
                
                # Clean up temp file
                os.unlink(tmp_path)
                
                logger.info(f"Successfully uploaded {safe_object_name} using temp file approach")
                return document_id
                
            except Exception as fallback_error:
                logger.error(f"Fallback upload also failed: {fallback_error}")
                raise

    def upload_chunk(self, document_id: str, chunk_id: str, chunk_text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Upload a single text chunk to MinIO

        Args:
            document_id: Document identifier
            chunk_id: Unique chunk identifier
            chunk_text: The text content of the chunk
            metadata: Optional metadata for the chunk

        Returns:
            bool: Success status
        """
        try:
            # Prepare chunk data
            chunk_data = {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "text": chunk_text,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            }

            # Convert to JSON
            json_data = json.dumps(chunk_data, ensure_ascii=False, indent=2)
            json_bytes = json_data.encode('utf-8')

            # Upload to chunks bucket with path structure: document_id/chunk_id.json
            object_name = f"{document_id}/{chunk_id}.json"

            self.client.put_object(
                settings.MINIO_BUCKET_CHUNKS,
                object_name,
                io.BytesIO(json_bytes),
                len(json_bytes),
                content_type='application/json'
            )

            logger.debug(f"Uploaded chunk {chunk_id} for document {document_id}")
            return True

        except S3Error as e:
            logger.error(f"Failed to upload chunk {chunk_id}: {e}")
            return False

    def upload_chunks(self, chunks: List[Dict[str, Any]], document_id: str) -> bool:
        """
        Upload text chunks to MinIO
        
        Args:
            chunks: List of chunk dictionaries with 'chunk_id' and 'text'
            document_id: Document identifier
        
        Returns:
            bool: Success status
        """
        try:
            # Combine all chunks into a single JSON document
            chunks_data = {
                "document_id": document_id,
                "chunks": chunks,
                "timestamp": datetime.now().isoformat(),
                "total_chunks": len(chunks)
            }
            
            # Convert to JSON
            json_data = json.dumps(chunks_data, ensure_ascii=False, indent=2)
            json_bytes = json_data.encode('utf-8')
            
            # Upload to chunks bucket
            object_name = f"{document_id}_chunks.json"
            self.client.put_object(
                settings.MINIO_BUCKET_CHUNKS,
                object_name,
                io.BytesIO(json_bytes),
                len(json_bytes),
                content_type='application/json'
            )
            
            logger.info(f"Uploaded {len(chunks)} chunks for document {document_id}")
            
            # Clear cache
            self._invalidate_cache(document_id)
            
            return True
            
        except S3Error as e:
            logger.error(f"Failed to upload chunks: {e}")
            return False
    
    def get_document(self, document_id: str) -> Optional[bytes]:
        """
        Retrieve document from MinIO with caching
        
        Args:
            document_id: Document identifier
        
        Returns:
            Document bytes or None if not found
        """
        # Check cache first
        cache_key = f"doc_{document_id}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            logger.debug(f"Retrieved document {document_id} from cache")
            return cached_data
        
        try:
            # List all objects in the bucket
            objects = self.client.list_objects(settings.MINIO_BUCKET_DOCS)
            
            # Find the document by checking metadata or name pattern
            for obj in objects:
                if document_id in obj.object_name:
                    # Get the object
                    response = self.client.get_object(
                        settings.MINIO_BUCKET_DOCS,
                        obj.object_name
                    )
                    data = response.read()
                    response.close()
                    
                    # Cache the result
                    self._add_to_cache(cache_key, data)
                    
                    logger.info(f"Retrieved document {document_id} from MinIO")
                    return data
            
            logger.warning(f"Document {document_id} not found in MinIO")
            return None
            
        except S3Error as e:
            logger.error(f"Failed to retrieve document: {e}")
            return None
    
    def get_chunks(self, document_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve chunks for a document with caching
        
        Args:
            document_id: Document identifier
        
        Returns:
            List of chunk dictionaries or None if not found
        """
        # Check cache first
        cache_key = f"chunks_{document_id}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            logger.debug(f"Retrieved chunks for {document_id} from cache")
            return cached_data
        
        try:
            object_name = f"{document_id}_chunks.json"
            
            # Get the object
            response = self.client.get_object(
                settings.MINIO_BUCKET_CHUNKS,
                object_name
            )
            
            # Read and parse JSON
            json_data = response.read().decode('utf-8')
            response.close()
            
            chunks_data = json.loads(json_data)
            chunks = chunks_data.get('chunks', [])
            
            # Cache the result
            self._add_to_cache(cache_key, chunks)
            
            logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")
            return chunks
            
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.info(f"No chunks found for document {document_id}")
            else:
                logger.error(f"Failed to retrieve chunks: {e}")
            return None
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete document and its chunks from MinIO
        
        Args:
            document_id: Document identifier
        
        Returns:
            bool: Success status
        """
        try:
            deleted_any = False
            
            # Delete from docs bucket
            objects = self.client.list_objects(settings.MINIO_BUCKET_DOCS)
            for obj in objects:
                if document_id in obj.object_name:
                    self.client.remove_object(
                        settings.MINIO_BUCKET_DOCS,
                        obj.object_name
                    )
                    logger.info(f"Deleted document object: {obj.object_name}")
                    deleted_any = True
            
            # Delete from chunks bucket
            try:
                chunk_object = f"{document_id}_chunks.json"
                self.client.remove_object(
                    settings.MINIO_BUCKET_CHUNKS,
                    chunk_object
                )
                logger.info(f"Deleted chunks: {chunk_object}")
                deleted_any = True
            except S3Error:
                pass  # Chunks might not exist
            
            # Clear cache
            self._invalidate_cache(document_id)
            
            return deleted_any
            
        except S3Error as e:
            logger.error(f"Failed to delete document: {e}")
            return False
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all documents in MinIO
        
        Returns:
            List of document metadata dictionaries
        """
        try:
            documents = []
            
            # List objects in docs bucket
            objects = self.client.list_objects(
                settings.MINIO_BUCKET_DOCS,
                recursive=True
            )
            
            for obj in objects:
                # Get object metadata
                stat = self.client.stat_object(
                    settings.MINIO_BUCKET_DOCS,
                    obj.object_name
                )
                
                doc_info = {
                    "filename": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "content_type": stat.content_type,
                    "metadata": stat.metadata
                }
                
                # Extract document_id from metadata if available
                if stat.metadata:
                    doc_info["document_id"] = stat.metadata.get("document_id", "")
                
                documents.append(doc_info)
            
            logger.info(f"Listed {len(documents)} documents from MinIO")
            return documents
            
        except S3Error as e:
            logger.error(f"Failed to list documents: {e}")
            return []
    
    def document_exists(self, document_id: str) -> bool:
        """
        Check if a document exists in MinIO

        Args:
            document_id: Document identifier

        Returns:
            bool: True if document exists
        """
        try:
            # Check in docs bucket
            objects = self.client.list_objects(settings.MINIO_BUCKET_DOCS)
            for obj in objects:
                if document_id in obj.object_name:
                    return True

            return False

        except S3Error as e:
            logger.error(f"Error checking document existence: {e}")
            return False

    def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """
        Get document metadata from MinIO

        Args:
            document_id: Document identifier

        Returns:
            Dictionary containing document metadata
        """
        try:
            # Try to find the document in the docs bucket
            objects = self.client.list_objects(
                settings.MINIO_BUCKET_DOCS,
                recursive=True
            )

            for obj in objects:
                if document_id in obj.object_name:
                    # Get object stat for metadata
                    stat = self.client.stat_object(
                        settings.MINIO_BUCKET_DOCS,
                        obj.object_name
                    )

                    # Extract metadata
                    metadata = {
                        "document_id": document_id,
                        "original_filename": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                        "content_type": stat.content_type if stat else "application/pdf"
                    }

                    # Add custom metadata if available
                    if stat and stat.metadata:
                        # MinIO metadata keys are lowercase
                        for key, value in stat.metadata.items():
                            # Map common metadata keys
                            if key == "x-amz-meta-original-filename":
                                metadata["original_filename"] = value
                            elif key == "x-amz-meta-document-id":
                                metadata["document_id"] = value
                            elif key == "x-amz-meta-upload-timestamp":
                                metadata["upload_timestamp"] = value
                            else:
                                # Store other metadata as-is
                                clean_key = key.replace("x-amz-meta-", "").replace("-", "_")
                                metadata[clean_key] = value

                    return metadata

            # Document not found, return default metadata
            logger.warning(f"Document {document_id} not found in MinIO")
            return {
                "document_id": document_id,
                "original_filename": f"{document_id}.pdf",
                "size": 0,
                "last_modified": None,
                "content_type": "application/pdf"
            }

        except S3Error as e:
            logger.error(f"Error getting document metadata: {e}")
            # Return safe default metadata on error
            return {
                "document_id": document_id,
                "original_filename": f"{document_id}.pdf",
                "size": 0,
                "last_modified": None,
                "content_type": "application/pdf",
                "error": str(e)
            }
    
    # Cache management methods
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired"""
        if key in self._cache:
            item = self._cache[key]
            if time.time() - item['timestamp'] < self._cache_ttl:
                return item['data']
            else:
                # Remove expired item
                del self._cache[key]
        return None
    
    def _add_to_cache(self, key: str, data: Any):
        """Add item to cache with size limit"""
        # Remove oldest items if cache is full
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest item
            oldest_key = min(self._cache.keys(), 
                           key=lambda k: self._cache[k]['timestamp'])
            del self._cache[oldest_key]
        
        self._cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def _invalidate_cache(self, document_id: str):
        """Remove document-related items from cache"""
        keys_to_remove = []
        for key in self._cache:
            if document_id in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._cache[key]
    
    def clear_cache(self):
        """Clear entire cache"""
        self._cache.clear()
        logger.info("Cleared MinIO cache")

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
        # No retry mechanism - try once and return result
        try:
            # Ensure raw-documents bucket exists
            raw_bucket = settings.MINIO_BUCKET_DOCS
            if not self.client.bucket_exists(raw_bucket):
                self.client.make_bucket(raw_bucket)
                logger.info(f"Created bucket: {raw_bucket}")

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
            logger.error(f"Failed to upload to raw-documents: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading to raw-documents: {e}")
            return False


# Singleton instance
storage = MinIOStorage()