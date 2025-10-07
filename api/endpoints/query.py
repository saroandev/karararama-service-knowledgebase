"""
Query endpoint for document search with multi-tenant scope support
"""
import datetime
import json
import logging
from urllib.parse import quote
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from openai import OpenAI

from schemas.api.requests.query import QueryRequest
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from schemas.api.responses.query import QueryResponse, QuerySource
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import retry_with_backoff
from api.core.embeddings import embedding_service
from app.config import settings
from app.core.storage import storage
from app.core.auth import UserContext, require_permission, get_current_user
from app.services.auth_service import get_auth_service_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
@retry_with_backoff(max_retries=3)
async def query_documents(
    request: QueryRequest,
    user: UserContext = Depends(get_current_user)  # Only JWT token required, no specific permission
) -> QueryResponse:
    """
    Multi-tenant query endpoint with scope-based search

    Requires:
    - Valid JWT token in Authorization header
    - Any authenticated user can query their accessible scopes

    Searches across user's accessible scopes based on search_scope parameter:
    - PRIVATE: Only user's private data (always accessible)
    - SHARED: Only organization shared data (if user has shared_data access)
    - ALL: Both private and shared data (based on user's data_access)
    """
#Buraya bir de PUBLIC eklenebilir.
    start_time = datetime.datetime.now()

    try:
        logger.info(f"🔍 Query from user {user.user_id} (org: {user.organization_id}): {request.question}")
        logger.info(f"🎯 Search scope: {request.search_scope}")

        # Determine which collections to search
        target_collections = _get_target_collections(user, request.search_scope)

        if not target_collections:
            logger.warning(f"No accessible collections for user {user.user_id} with scope {request.search_scope}")
            return _create_empty_response(request, start_time)

        # Generate query embedding
        query_embedding = embedding_service.generate_embedding(request.question)

        # Search across all target collections and merge results
        all_search_results = []
        for collection_info in target_collections:
            collection = collection_info["collection"]
            scope_label = collection_info["scope_label"]

            logger.info(f"🔎 Searching in collection: {collection.name} ({scope_label})")

            try:
                # Vector search
                search_results = collection.search(
                    [query_embedding],
                    'embedding',
                    {'metric_type': 'COSINE'},
                    limit=request.top_k,
                    expr=None,  # No filters within scope
                    output_fields=['document_id', 'chunk_index', 'text', 'metadata']
                )

                # Tag results with scope info
                for result in search_results[0]:
                    result._scope_label = scope_label
                    all_search_results.append(result)

                logger.info(f"✅ Found {len(search_results[0])} results in {scope_label}")

            except Exception as e:
                logger.error(f"❌ Search failed in collection {collection.name}: {e}")
                continue

        # Sort all results by score (descending)
        all_search_results.sort(key=lambda x: x.score, reverse=True)

        # Limit to top_k
        all_search_results = all_search_results[:request.top_k]

        if not all_search_results:
            return _create_empty_response(request, start_time)

        # Track total sources retrieved (before filtering)
        total_sources_retrieved = len(all_search_results)

        # Prepare context
        high_confidence_sources = []
        low_confidence_sources = []
        context_parts = []

        # Cache for document metadata
        doc_metadata_cache = {}

        for i, result in enumerate(all_search_results):
            score = result.score
            scope_label = getattr(result, '_scope_label', 'unknown')

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

            # Get the original filename from metadata
            document_title = meta_dict.get('document_title', 'Unknown')

            # Try to get better metadata from MinIO if needed
            if doc_id not in doc_metadata_cache:
                doc_metadata_cache[doc_id] = storage.get_document_metadata(doc_id)

            # Use document title from Milvus metadata, fallback to MinIO metadata
            if document_title and document_title != 'Unknown':
                original_filename = f"{document_title}.pdf" if not document_title.endswith('.pdf') else document_title
            elif doc_id in doc_metadata_cache:
                original_filename = doc_metadata_cache[doc_id].get("original_filename", f'{doc_id}.pdf')
            else:
                original_filename = f'{doc_id}.pdf'

            doc_title = document_title if document_title != 'Unknown' else original_filename.replace('.pdf', '')
            page_num = meta_dict.get('page_number', 0)
            created_at = meta_dict.get('created_at', 0)

            # Generate document URL for MinIO console (properly encoded)
            encoded_filename = quote(original_filename)
            document_url = f"http://localhost:9001/browser/raw-documents/{doc_id}/{encoded_filename}"

            # Create source object
            source = QuerySource(
                rank=i + 1,
                score=round(score, 3),
                document_id=doc_id,
                document_name=original_filename,
                document_title=doc_title,
                document_url=document_url,
                page_number=page_num,
                text_preview=text[:200] + "..." if len(text) > 200 else text,
                created_at=created_at
            )

            # Filter by relevance score
            if score >= request.min_relevance_score:
                high_confidence_sources.append(source)
                # Only add high-confidence sources to context (limited by max_sources_in_context)
                if len(high_confidence_sources) <= request.max_sources_in_context:
                    context_parts.append(f"[Kaynak {len(high_confidence_sources)} - Sayfa {page_num}]: {text}")
            else:
                # Low confidence source
                if request.include_low_confidence_sources:
                    low_confidence_sources.append(source)

        # Generate answer
        context = "\n\n".join(context_parts)

        # Generate answer using OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        chat_response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
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
        model_used = settings.OPENAI_MODEL

        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        # Get token usage from OpenAI response
        tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0

        # Report usage to auth service
        auth_client = get_auth_service_client()
        remaining_credits = user.remaining_credits

        logger.info(f"[CONSUME] Starting usage reporting to auth service")
        logger.info(f"[CONSUME] User ID: {user.user_id}")
        logger.info(f"[CONSUME] Service Type: rag_query")
        logger.info(f"[CONSUME] Tokens Used: {tokens_used}")
        logger.info(f"[CONSUME] Processing Time: {processing_time:.2f}s")

        try:
            usage_result = await auth_client.consume_usage(
                user_id=user.user_id,
                service_type="rag_query",
                tokens_used=tokens_used,
                processing_time=processing_time,
                metadata={
                    "question_length": len(request.question),
                    "sources_count": len(high_confidence_sources),
                    "model": model_used,
                    "top_k": request.top_k,
                    "min_relevance_score": request.min_relevance_score
                }
            )

            logger.info(f"[CONSUME] ✅ Auth service response: {usage_result}")

            # Update credits from auth service response
            if usage_result.get("remaining_credits") is not None:
                remaining_credits = usage_result.get("remaining_credits")
                logger.info(f"[CONSUME] Updated remaining credits: {remaining_credits}")

        except Exception as e:
            # Log but don't fail the request (already processed)
            logger.error(f"[CONSUME] ❌ Failed to report usage to auth service: {str(e)}")
            import traceback
            logger.error(f"[CONSUME] Traceback: {traceback.format_exc()}")

        logger.info(
            f"Query completed in {processing_time:.2f}s | "
            f"Retrieved: {total_sources_retrieved} | "
            f"High confidence: {len(high_confidence_sources)} | "
            f"Low confidence: {len(low_confidence_sources)} | "
            f"Threshold: {request.min_relevance_score}"
        )

        # Check if we have any high-confidence sources
        if not high_confidence_sources:
            return QueryResponse(
                answer="İlgili bilgi bulunamadı. Lütfen sorunuzu farklı şekilde ifade etmeyi deneyin veya minimum alakalılık skorunu düşürün.",
                sources=[],
                processing_time=processing_time,
                model_used=model_used,
                tokens_used=0,
                remaining_credits=remaining_credits,
                total_sources_retrieved=total_sources_retrieved,
                sources_after_filtering=0,
                min_score_applied=request.min_relevance_score,
                low_confidence_sources=low_confidence_sources if request.include_low_confidence_sources else None
            )

        return QueryResponse(
            answer=answer,
            sources=high_confidence_sources,
            processing_time=processing_time,
            model_used=model_used,
            tokens_used=tokens_used,
            remaining_credits=remaining_credits,
            total_sources_retrieved=total_sources_retrieved,
            sources_after_filtering=len(high_confidence_sources),
            min_score_applied=request.min_relevance_score,
            low_confidence_sources=low_confidence_sources if request.include_low_confidence_sources else None
        )

    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


def _get_target_collections(user: UserContext, search_scope: DataScope) -> List[dict]:
    """
    Get list of collections to search based on user context and search scope

    Args:
        user: User context with organization and access scope
        search_scope: Requested search scope (PRIVATE, SHARED, or ALL)

    Returns:
        List of dicts with 'collection' and 'scope_label' keys
    """
    collections = []

    if search_scope == DataScope.ALL:
        # Search in all accessible scopes
        # Private data
        if user.data_access.own_data:
            private_scope = ScopeIdentifier(
                organization_id=user.organization_id,
                scope_type=DataScope.PRIVATE,
                user_id=user.user_id
            )
            try:
                collection = milvus_manager.get_collection(private_scope)
                collections.append({
                    "collection": collection,
                    "scope_label": "private"
                })
            except Exception as e:
                logger.warning(f"Could not load private collection: {e}")

        # Shared data
        if user.data_access.shared_data:
            shared_scope = ScopeIdentifier(
                organization_id=user.organization_id,
                scope_type=DataScope.SHARED
            )
            try:
                collection = milvus_manager.get_collection(shared_scope)
                collections.append({
                    "collection": collection,
                    "scope_label": "shared"
                })
            except Exception as e:
                logger.warning(f"Could not load shared collection: {e}")

    elif search_scope == DataScope.PRIVATE:
        # Only private data
        if not user.data_access.own_data:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to private data"
            )

        private_scope = ScopeIdentifier(
            organization_id=user.organization_id,
            scope_type=DataScope.PRIVATE,
            user_id=user.user_id
        )
        collection = milvus_manager.get_collection(private_scope)
        collections.append({
            "collection": collection,
            "scope_label": "private"
        })

    elif search_scope == DataScope.SHARED:
        # Only shared data
        if not user.data_access.shared_data:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to shared data"
            )

        shared_scope = ScopeIdentifier(
            organization_id=user.organization_id,
            scope_type=DataScope.SHARED
        )
        collection = milvus_manager.get_collection(shared_scope)
        collections.append({
            "collection": collection,
            "scope_label": "shared"
        })

    return collections


def _create_empty_response(request: QueryRequest, start_time: datetime.datetime) -> QueryResponse:
    """Create empty response when no results found"""
    processing_time = (datetime.datetime.now() - start_time).total_seconds()

    return QueryResponse(
        answer="İlgili bilgi bulunamadı.",
        sources=[],
        processing_time=processing_time,
        model_used=settings.OPENAI_MODEL,
        total_sources_retrieved=0,
        sources_after_filtering=0,
        min_score_applied=request.min_relevance_score
    )