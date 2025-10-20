"""
Query endpoint for document search with multi-tenant scope support

Refactored with Orchestrator pattern for clean separation of concerns.
All search logic is now handled by the QueryOrchestrator.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Request

from schemas.api.requests.query import QueryRequest
from schemas.api.responses.query import QueryResponse
from api.core.dependencies import retry_with_backoff
from app.core.auth import UserContext, get_current_user
from app.core.orchestrator import QueryOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat/process", response_model=QueryResponse)
@retry_with_backoff(max_retries=3)
async def query_documents(
    request: QueryRequest,
    http_request: Request,
    user: UserContext = Depends(get_current_user)
) -> QueryResponse:
    """
    Multi-tenant query endpoint with multi-source search

    Requires:
    - Valid JWT token in Authorization header
    - Any authenticated user can query their accessible sources

    Searches across selected sources based on sources parameter (list):
    - PRIVATE: User's private data (requires own_data access)
    - SHARED: Organization shared data (requires shared_data access)
    - MEVZUAT: External legislation database (Global DB)
    - KARAR: External court decisions database (Global DB)
    - ALL: Expands to both PRIVATE and SHARED

    User can select multiple sources: ["private", "mevzuat"] or ["karar"] or ["mevzuat", "karar"]

    Architecture:
    This endpoint now uses the Orchestrator pattern. The QueryOrchestrator coordinates:
    1. CollectionServiceHandler for collection-based searches (via HTTP)
    2. ExternalServiceHandler for MEVZUAT/KARAR sources (via HTTP)
    3. ResultAggregator for merging results and generating answers

    All handlers execute in parallel for optimal performance.
    """
    try:
        logger.info(f"🔍 Query from user {user.user_id} (org: {user.organization_id}): {request.question}")
        logger.info(f"🎯 Requested sources: {request.sources}")

        # Extract JWT token for external service authentication
        auth_header = http_request.headers.get("Authorization", "")
        user_token = ""
        if auth_header.startswith("Bearer "):
            user_token = auth_header.replace("Bearer ", "")

        # Create orchestrator and execute query
        orchestrator = QueryOrchestrator()

        response = await orchestrator.execute_query(
            request=request,
            user=user,
            user_token=user_token
        )

        return response

    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
