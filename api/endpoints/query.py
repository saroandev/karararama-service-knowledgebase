"""
Query endpoint for document search with multi-tenant scope support
"""
import datetime
import json
import logging
from urllib.parse import quote
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request
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
from app.services.global_db_service import get_global_db_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
@retry_with_backoff(max_retries=3)
async def query_documents(
    request: QueryRequest,
    http_request: Request,
    user: UserContext = Depends(get_current_user)  # Only JWT token required, no specific permission
) -> QueryResponse:
    """
    Multi-tenant query endpoint with multi-source search

    Requires:
    - Valid JWT token in Authorization header
    - Any authenticated user can query their accessible sources

    Searches across selected sources based on sources parameter (list):
    - PRIVATE: User's private data (requires own_data access)
    - SHARED: Organization shared data (requires shared_data access)
    - PUBLIC: External public data service (not yet implemented)
    - ALL: Expands to both PRIVATE and SHARED

    User can select multiple sources: ["private", "shared"] or just ["private"]
    """
    start_time = datetime.datetime.now()

    try:
        logger.info(f"🔍 Query from user {user.user_id} (org: {user.organization_id}): {request.question}")
        logger.info(f"🎯 Requested sources: {[s.value for s in request.sources]}")

        # Determine which collections to search
        target_collections = _get_target_collections(user, request.sources)

        # Check if we have any collections or PUBLIC source
        has_public_source = DataScope.PUBLIC in request.sources
        if not target_collections and not has_public_source:
            logger.warning(f"No accessible sources for user {user.user_id} with sources {request.sources}")
            return _create_empty_response(request, start_time)

        # Generate query embedding (only if we have Milvus collections to search)
        query_embedding = None
        if target_collections:
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

        # Check if PUBLIC source is requested
        public_answer = None
        public_sources = []
        if DataScope.PUBLIC in request.sources:
            logger.info("🌍 Querying Global DB service for PUBLIC sources...")
            try:
                # Extract JWT token from authorization header
                auth_header = http_request.headers.get("Authorization", "")
                user_token = ""
                if auth_header.startswith("Bearer "):
                    user_token = auth_header.replace("Bearer ", "")
                else:
                    logger.warning("⚠️ No valid Authorization header found for PUBLIC query")

                # Get global DB client and call search
                global_db_client = get_global_db_client()

                external_response = await global_db_client.search_public(
                    question=request.question,
                    user_token=user_token,
                    top_k=request.top_k,
                    min_relevance_score=request.min_relevance_score
                )

                if external_response.get("success"):
                    public_answer = external_response.get("answer", "")
                    public_sources = external_response.get("sources", [])

                    logger.info(f"✅ Global DB returned {len(public_sources)} sources")

                    # Convert external sources to our internal format
                    for source in public_sources:
                        # Create a mock result object that mimics Milvus result structure
                        class PublicResult:
                            def __init__(self, source_data):
                                self.score = source_data.get("score", 0.0)
                                self._scope_label = "public"
                                self.entity = type('obj', (object,), {
                                    'document_id': source_data.get("document_id", "unknown"),
                                    'text': source_data.get("text", ""),
                                    'metadata': {
                                        'document_title': source_data.get("document_name", "Unknown"),
                                        'page_number': source_data.get("page_number", 0),
                                        'created_at': source_data.get("created_at", 0),
                                        'document_url': source_data.get("document_url", "")
                                    }
                                })()

                        all_search_results.append(PublicResult(source))

                else:
                    logger.warning(f"⚠️ Global DB query failed: {external_response.get('error', 'Unknown error')}")

            except Exception as e:
                logger.error(f"❌ Failed to query Global DB service: {str(e)}")
                # Continue with Milvus results only
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

        # Sort all results by score (descending)
        all_search_results.sort(key=lambda x: x.score, reverse=True)

        # Limit to top_k
        all_search_results = all_search_results[:request.top_k]

        # Check if we have any results (or will use public answer)
        if not all_search_results and not public_answer:
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
            page_num = meta_dict.get('page_number', 0)
            created_at = meta_dict.get('created_at', 0)

            # Handle URL differently based on scope
            if scope_label == 'public':
                # External source - use URL from metadata
                document_url = meta_dict.get('document_url', '#')
                original_filename = document_title if document_title != 'Unknown' else 'Public Document'
                doc_title = document_title
            else:
                # Internal source (private/shared) - generate MinIO URL
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

        # Determine if we should use external answer or generate our own
        # Use external answer if PUBLIC is the only source requested
        if public_answer and request.sources == [DataScope.PUBLIC]:
            # Use external service answer directly
            answer = public_answer
            model_used = "OneDocs Global DB"
            tokens_used = 0  # External service tokens not tracked here
            logger.info("✅ Using answer from Global DB service")
        elif high_confidence_sources:
            # Generate answer using OpenAI with our sources
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
            tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0
        else:
            # No high confidence sources found
            answer = "İlgili bilgi bulunamadı. Lütfen sorunuzu farklı şekilde ifade etmeyi deneyin."
            model_used = settings.OPENAI_MODEL
            tokens_used = 0

        processing_time = (datetime.datetime.now() - start_time).total_seconds()

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


def _get_target_collections(user: UserContext, sources: List[DataScope]) -> List[dict]:
    """
    Get list of collections to search based on user context and selected sources

    Args:
        user: User context with organization and access scope
        sources: List of requested data sources (PRIVATE, SHARED, PUBLIC, or ALL)

    Returns:
        List of dicts with 'collection' and 'scope_label' keys
    """
    collections = []

    # Expand ALL to both PRIVATE and SHARED
    expanded_sources = []
    for source in sources:
        if source == DataScope.ALL:
            expanded_sources.extend([DataScope.PRIVATE, DataScope.SHARED])
        else:
            expanded_sources.append(source)

    # Remove duplicates while preserving order
    seen = set()
    unique_sources = []
    for source in expanded_sources:
        if source not in seen:
            seen.add(source)
            unique_sources.append(source)

    # Process each requested source
    for source in unique_sources:
        if source == DataScope.PRIVATE:
            # Check access permission
            if not user.data_access.own_data:
                logger.warning(f"User {user.user_id} requested PRIVATE data but doesn't have own_data access")
                continue

            # Get private collection
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
                logger.info(f"✅ Added PRIVATE collection: {collection.name}")
            except Exception as e:
                logger.warning(f"Could not load private collection: {e}")

        elif source == DataScope.SHARED:
            # Check access permission
            if not user.data_access.shared_data:
                logger.warning(f"User {user.user_id} requested SHARED data but doesn't have shared_data access")
                continue

            # Get shared collection
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
                logger.info(f"✅ Added SHARED collection: {collection.name}")
            except Exception as e:
                logger.warning(f"Could not load shared collection: {e}")

        elif source == DataScope.PUBLIC:
            # PUBLIC is handled separately in query_documents() via Global DB service
            logger.info("🌍 PUBLIC source requested - will query Global DB service")
            continue

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