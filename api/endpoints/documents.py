"""
Documents management endpoints
"""
import datetime
import json
import logging
from typing import List
from fastapi import APIRouter, HTTPException

from schemas.responses.document import DocumentInfo
from api.core.milvus_manager import milvus_manager
from app.core.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents", response_model=List[DocumentInfo])
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


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and all its chunks
    """
    # Validate document ID format
    if not document_id or not document_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_DOCUMENT_ID",
                    "message": "Geçersiz doküman ID'si",
                    "details": "Doküman ID'si boş olamaz"
                }
            }
        )

    try:
        # Get Milvus collection
        try:
            collection = milvus_manager.get_collection()
        except Exception as e:
            logger.error(f"Milvus connection error: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Veritabanı bağlantısı kurulamadı",
                        "details": f"Milvus servisine erişilemiyor: {str(e)}"
                    }
                }
            )

        # Find document chunks
        chunks = collection.query(
            expr=f'document_id == "{document_id}"',
            output_fields=['id', 'metadata']
        )

        if not chunks:
            logger.info(f"Document not found: {document_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": {
                        "code": "DOCUMENT_NOT_FOUND",
                        "message": "Doküman bulunamadı",
                        "details": f"'{document_id}' ID'sine sahip doküman mevcut değil"
                    }
                }
            )

        # Get document metadata for response
        doc_metadata = chunks[0].get('metadata', {})
        if isinstance(doc_metadata, str):
            import json
            doc_metadata = json.loads(doc_metadata)
        doc_title = doc_metadata.get('document_title', 'Unknown')

        # Delete chunks from Milvus
        ids_to_delete = [chunk['id'] for chunk in chunks]
        try:
            collection.delete(expr=f"id in {ids_to_delete}")
            logger.info(f"Deleted {len(chunks)} chunks from Milvus for document {document_id}")
            milvus_deleted = True
        except Exception as e:
            logger.error(f"Failed to delete from Milvus: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": {
                        "code": "MILVUS_DELETE_FAILED",
                        "message": "Veritabanından silme işlemi başarısız",
                        "details": f"Milvus silme hatası: {str(e)}"
                    }
                }
            )

        # Try to delete from MinIO as well
        minio_deleted = False
        minio_error = None
        try:
            storage.delete_document(document_id)
            logger.info(f"Deleted document {document_id} from MinIO")
            minio_deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete from MinIO: {e}")
            minio_error = str(e)

        # Prepare response based on deletion results
        if milvus_deleted and minio_deleted:
            return {
                "success": True,
                "document_id": document_id,
                "document_title": doc_title,
                "deleted_chunks": len(chunks),
                "message": f"'{doc_title}' dokümanı ve {len(chunks)} chunk başarıyla silindi",
                "details": {
                    "milvus_status": "success",
                    "minio_status": "success"
                }
            }
        elif milvus_deleted and not minio_deleted:
            # Partial success - document removed from search but files remain
            return {
                "success": True,
                "document_id": document_id,
                "document_title": doc_title,
                "deleted_chunks": len(chunks),
                "message": f"'{doc_title}' dokümanı veritabanından silindi ancak dosya deposundan silinemedi",
                "warning": f"MinIO silme hatası: {minio_error}",
                "details": {
                    "milvus_status": "success",
                    "minio_status": "failed",
                    "minio_error": minio_error
                }
            }

    except HTTPException:
        # Re-raise HTTP exceptions with our custom format
        raise
    except Exception as e:
        logger.error(f"Unexpected delete document error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Beklenmeyen bir hata oluştu",
                    "details": f"Silme işlemi sırasında hata: {str(e)}"
                }
            }
        )