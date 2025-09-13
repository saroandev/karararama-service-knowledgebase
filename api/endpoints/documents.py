"""
Documents management endpoints
"""
import datetime
import json
import logging
from typing import List
from fastapi import APIRouter, HTTPException

from api.models.responses import DocumentInfo
from api.core.milvus_manager import milvus_manager
from app.storage import storage

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
            storage.delete_document(document_id)
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