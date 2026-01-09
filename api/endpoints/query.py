"""
Query endpoint for document search with multi-tenant scope support

SIMPLIFIED VERSION: This endpoint now only handles collection queries.
For multi-source queries (including external sources like mevzuat, karar),
use the orchestrator service at onedocs-service-orchestrator.
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import JSONResponse

from schemas.api.requests.query import QueryRequest, QueryOptions
from schemas.api.requests.collection import CollectionQueryRequest
from schemas.api.responses.query import QueryResponse, QuerySource
from schemas.api.responses.collection import CollectionQueryResponse
from api.core.dependencies import retry_with_backoff
from app.core.auth import UserContext, get_current_user
from app.core.storage import storage
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# Import collections query function
from api.endpoints.collections_query import query_collections


@router.post("/chat/process", response_model=QueryResponse)
@retry_with_backoff(max_retries=3)
async def query_documents(
    request: QueryRequest,
    http_request: Request,
    user: UserContext = Depends(get_current_user)
) -> QueryResponse:
    """
    Collection-only query endpoint (simplified).

    This endpoint handles ONLY collection queries.
    For multi-source queries including external sources (mevzuat, karar, etc.),
    use the orchestrator service.

    Requires:
    - Valid JWT token in Authorization header
    - **conversation_id in request body is REQUIRED**
    - At least one collection must be specified

    Note:
    - If 'sources' parameter is provided, returns 400 error
    - Use orchestrator service for external source queries
    """
    start_time = time.time()

    try:
        logger.info(f"🔍 Query from user {user.user_id} (org: {user.organization_id}): {request.question}")

        # Check if sources are provided - not supported in this simplified endpoint
        if request.sources and len(request.sources) > 0:
            logger.warning(f"❌ Sources parameter not supported in this endpoint: {request.sources}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "sources_not_supported",
                    "message": "Bu endpoint sadece collection sorgularını destekler. "
                               "External sources (mevzuat, karar, vb.) için orchestrator servisini kullanın.",
                    "hint": "Use orchestrator service at /chat/process for multi-source queries"
                }
            )

        # Check if collections are provided
        if not request.collections or len(request.collections) == 0:
            logger.warning("❌ No collections specified")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "collections_required",
                    "message": "En az bir collection belirtmelisiniz.",
                    "hint": "Provide collections parameter with at least one collection filter"
                }
            )

        logger.info(f"📦 Collections: {[f'{c.name}({c.scopes})' for c in request.collections]}")

        # Build collection query request
        collection_request = CollectionQueryRequest(
            question=request.question,
            collections=request.collections,
            top_k=request.top_k,
            min_relevance_score=request.min_relevance_score,
            search_mode=request.search_mode,
            options=request.options or QueryOptions()
        )

        # Execute collection query
        collection_response: CollectionQueryResponse = await query_collections(
            request=collection_request,
            user=user
        )

        # Convert CollectionQueryResponse to QueryResponse format
        processing_time = time.time() - start_time

        # Convert results to QuerySource format
        citations = []
        for result in collection_response.results:
            # Generate presigned URL for the document
            try:
                # Determine scope and build path
                scope = result.source_type  # "private" or "shared"
                collection_name = result.collection_name

                if scope == "private":
                    minio_path = f"users/{user.user_id}/collections/{collection_name}/docs/{result.document_id}"
                else:
                    minio_path = f"shared/collections/{collection_name}/docs/{result.document_id}"

                # Get presigned URL
                document_url = storage.client_manager.generate_presigned_url(
                    bucket_name=f"org-{user.organization_id}",
                    object_name=minio_path,
                    expires_hours=1
                )
            except Exception as e:
                logger.warning(f"Failed to generate presigned URL for {result.document_id}: {e}")
                document_url = ""

            # Build metadata
            metadata = {
                "filename": result.metadata.get("filename", result.document_title) if result.metadata else result.document_title,
                "title": result.document_title,
                "bucket": f"org-{user.organization_id}",
                "scope": result.source_type,
                "page_number": result.page_number,
                "collection_name": result.collection_name
            }

            # Add any additional metadata
            if result.metadata:
                for key, value in result.metadata.items():
                    if key not in metadata:
                        metadata[key] = value

            citations.append(QuerySource(
                document_id=result.document_id,
                chunk_index=result.chunk_index,
                text=result.text,
                relevance_score=result.score / 100.0,  # Convert from 0-100 to 0-1
                document_url=document_url,
                metadata=metadata
            ))

        # Build response
        response = QueryResponse(
            answer=collection_response.generated_answer or "İlgili bilgi bulunamadı.",
            role="assistant",
            conversation_id=request.conversation_id,
            citations=citations,
            processing_time=processing_time,
            model_used=settings.OPENAI_MODEL,
            tokens_used=0,  # Will be tracked separately
            remaining_credits=0,  # Will be tracked separately
            total_sources_retrieved=collection_response.total_results,
            sources_after_filtering=len(citations),
            min_score_applied=request.min_relevance_score,
            low_confidence_citations=None
        )

        logger.info(f"✅ Query completed in {processing_time:.3f}s with {len(citations)} citations")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response.model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
