"""
Collection query endpoint - Handles semantic search within collections

This endpoint provides the Milvus search logic for collections,
isolating it from the orchestrator for clean architecture.
"""

import logging
import time
import json
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from schemas.api.requests.collection import CollectionQueryRequest
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from schemas.api.requests.query import QueryOptions
from schemas.api.responses.collection import CollectionQueryResponse, CollectionSearchResult
from api.core.milvus_manager import milvus_manager
from api.core.embeddings import embedding_service
from app.core.auth import UserContext, get_current_user
from app.core.orchestrator.prompts import PromptTemplate
from app.config import settings
from openai import OpenAI

logger = logging.getLogger(__name__)
router = APIRouter()


def _generate_collection_answer(
    results: List[CollectionSearchResult],
    question: str,
    options: QueryOptions
) -> tuple[str, int]:
    """
    Generate answer from collection search results using LLM

    Args:
        results: Search results from collections
        question: User's question
        options: Query options (tone, lang, citations)

    Returns:
        (generated_answer, tokens_used)
    """
    if not results:
        if options.lang == "eng":
            return "No relevant information found in the specified collections.", 0
        return "Belirtilen collection'larda ilgili bilgi bulunamadı.", 0

    try:
        # Build context from results with citations
        context_parts = []
        for i, result in enumerate(results, 1):
            if options.citations:
                context_parts.append(
                    f"[Kaynak {i} - Sayfa {result.page_number} - {result.collection_name}]: {result.text}"
                )
            else:
                context_parts.append(result.text)

        context = "\n\n".join(context_parts)

        # Get collection-specific prompt (use "private" as base for collections)
        # Collections are user-specific organizational units
        base_prompt = """Sen kullanıcının collection doküman asistanısın.

GÖREVİN:
• Collection'lardaki belgelerden faydalanarak soruları cevaplamak
• Yanıtlarını "Collection belgelerinize göre..." şeklinde başlat
• Türkçe dilbilgisi kurallarına uygun, akıcı bir dille yazmak
• Her zaman kaynak numaralarını belirtmek (Örn: [Kaynak 1], [Kaynak 2])

CEVAP FORMATI:
1. "Collection belgelerinize göre," ile başla
2. Soruya doğrudan ve özlü cevap ver
3. Gerekirse madde madde açıkla
4. Her bilgi için kaynak numarasını ve collection adını belirt

ÖNEMLI:
• Sadece verilen kaynaklardaki bilgileri kullan
• Collection adlarını belirtmeyi unutma
• Belirsizlik varsa bunu belirt"""

        # Add tone modifier if specified
        if options.tone != "resmi":
            tone_modifier = PromptTemplate.TONE_MODIFIERS.get(options.tone, "")
            base_prompt += tone_modifier

        # Add strong language instruction
        language_modifiers = {
            "tr": "\n\n⚠️ ÇOK ÖNEMLİ - DİL: Tüm yanıtını MUTLAKA TÜRKÇE olarak ver. Her cümleyi, her kelimeyi Türkçe yaz. İngilizce kelime kullanma.",
            "eng": "\n\n⚠️ CRITICAL - LANGUAGE: You MUST respond ENTIRELY in ENGLISH. Every sentence, every word must be in English. Do NOT use Turkish words."
        }
        lang_modifier = language_modifiers.get(options.lang, language_modifiers["tr"])
        base_prompt += lang_modifier

        # Prepare user message based on language
        if options.lang == "eng":
            user_message = f"""Context from collections:

{context}

Question: {question}

Provide a comprehensive answer based on the sources above."""
        else:
            user_message = f"""Collection'lardan gelen bilgiler:

{context}

Soru: {question}

Yukarıdaki kaynaklara dayanarak kapsamlı bir yanıt ver."""

        # Call OpenAI API
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        chat_response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": base_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=700,
            temperature=0.7
        )

        answer = chat_response.choices[0].message.content
        tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0

        logger.info(f"✅ Generated answer using {settings.OPENAI_MODEL} ({tokens_used} tokens)")
        return answer, tokens_used

    except Exception as e:
        logger.error(f"❌ Failed to generate answer: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Return fallback message
        if options.lang == "eng":
            return "An error occurred while generating the answer. Please try again.", 0
        return "Cevap üretilirken bir hata oluştu. Lütfen tekrar deneyin.", 0


@router.post("/collections/query", response_model=CollectionQueryResponse)
async def query_collections(
    request: CollectionQueryRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Search within specified collections using semantic search

    This endpoint:
    1. Takes a question and list of collections with scopes
    2. Generates embedding for the question
    3. Searches each collection in specified scopes
    4. Returns ranked results with optional generated answer

    Requires:
    - Valid JWT token
    - Access permissions for specified scopes
    """
    start_time = time.time()

    logger.info(f"🔍 Collection query from user {user.user_id}")
    logger.info(f"📝 Question: {request.question}")
    logger.info(f"📦 Collections: {[f'{c.name}({c.scopes})' for c in request.collections]}")

    # Log query options
    options = request.options or QueryOptions()
    logger.info(f"⚙️ Query options: tone={options.tone}, citations={options.citations}, lang={options.lang}")

    try:
        # 1. Generate query embedding
        logger.info("Generating embedding for question...")
        query_embedding = embedding_service.generate_embedding(request.question)

        # 2. Get target collections
        collections_to_search = []
        for collection_filter in request.collections:
            collection_name = collection_filter.name
            filter_scopes = collection_filter.scopes

            logger.info(f"📦 '{collection_name}' - scopes: {[s.value for s in filter_scopes]}")

            # Search in each scope
            for scope in filter_scopes:
                if scope == DataScope.PRIVATE:
                    # Check access
                    if not user.data_access.own_data:
                        logger.warning(f"❌ User {user.user_id} doesn't have own_data access")
                        continue

                    # Create scope identifier
                    private_scope = ScopeIdentifier(
                        organization_id=user.organization_id,
                        scope_type=DataScope.PRIVATE,
                        user_id=user.user_id,
                        collection_name=collection_name
                    )

                    try:
                        collection = milvus_manager.get_collection(private_scope, auto_create=False)
                        collections_to_search.append({
                            "collection": collection,
                            "scope_label": f"private/{collection_name}",
                            "collection_name": collection_name
                        })
                        logger.info(f"✅ '{collection_name}' private collection found: {collection.name}")
                    except Exception as e:
                        # Enhanced logging for collection not found
                        milvus_collection_name = private_scope.get_collection_name(settings.EMBEDDING_DIMENSION)
                        if "does not exist" in str(e).lower() or "not exist" in str(e).lower():
                            logger.warning(f"⚠️ Collection '{collection_name}' not found in PRIVATE scope (Milvus: {milvus_collection_name}). User may need to create it first.")
                        else:
                            logger.warning(f"⚠️ Collection '{collection_name}' error in PRIVATE scope: {str(e)}")

                elif scope == DataScope.SHARED:
                    # Check access
                    if not user.data_access.shared_data:
                        logger.warning(f"❌ User {user.user_id} doesn't have shared_data access")
                        continue

                    # Create scope identifier
                    shared_scope = ScopeIdentifier(
                        organization_id=user.organization_id,
                        scope_type=DataScope.SHARED,
                        collection_name=collection_name
                    )

                    try:
                        collection = milvus_manager.get_collection(shared_scope, auto_create=False)
                        collections_to_search.append({
                            "collection": collection,
                            "scope_label": f"shared/{collection_name}",
                            "collection_name": collection_name
                        })
                        logger.info(f"✅ '{collection_name}' shared collection found: {collection.name}")
                    except Exception as e:
                        # Enhanced logging for collection not found
                        milvus_collection_name = shared_scope.get_collection_name(settings.EMBEDDING_DIMENSION)
                        if "does not exist" in str(e).lower() or "not exist" in str(e).lower():
                            logger.warning(f"⚠️ Collection '{collection_name}' not found in SHARED scope (Milvus: {milvus_collection_name}). Admin may need to create it first.")
                        else:
                            logger.warning(f"⚠️ Collection '{collection_name}' error in SHARED scope: {str(e)}")

        if not collections_to_search:
            # Enhanced logging when no collections are found
            requested_collections = [f"'{c.name}' ({[s.value for s in c.scopes]})" for c in request.collections]
            logger.warning(f"❌ No accessible collections found for user {user.user_id}")
            logger.warning(f"📦 Requested collections: {', '.join(requested_collections)}")
            logger.warning(f"💡 Hint: User may need to create these collections first using POST /collections")
            processing_time = time.time() - start_time
            return CollectionQueryResponse(
                results=[],
                generated_answer=None,
                success=True,
                processing_time=processing_time,
                collections_searched=0,
                total_results=0,
                options_used=options
            )

        logger.info(f"📊 Searching in {len(collections_to_search)} collection(s)")

        # 3. Search across all collections
        all_results = []
        for collection_info in collections_to_search:
            collection = collection_info["collection"]
            scope_label = collection_info["scope_label"]
            collection_name = collection_info["collection_name"]

            logger.info(f"🔎 Searching in {collection.name} ({scope_label})")

            try:
                search_results = collection.search(
                    [query_embedding],
                    'embedding',
                    {'metric_type': 'COSINE'},
                    limit=request.top_k,
                    expr=None,
                    output_fields=['document_id', 'chunk_index', 'text', 'metadata']
                )

                # Convert Milvus results to CollectionSearchResult objects
                for result in search_results[0]:
                    score = result.score
                    doc_id = result.entity.document_id
                    chunk_index = result.entity.chunk_index if hasattr(result.entity, 'chunk_index') else 0
                    text = result.entity.text if hasattr(result.entity, 'text') else ''
                    metadata = result.entity.metadata if hasattr(result.entity, 'metadata') else {}

                    # Parse metadata
                    if isinstance(metadata, str):
                        meta_dict = json.loads(metadata)
                    else:
                        meta_dict = metadata if metadata else {}

                    # Determine source type from scope_label
                    source_type = "private" if "private" in scope_label else "shared"

                    all_results.append(CollectionSearchResult(
                        score=score,
                        document_id=doc_id,
                        text=text,
                        source_type=source_type,
                        chunk_index=chunk_index,
                        page_number=meta_dict.get('page_number', 0),
                        document_title=meta_dict.get('document_title', 'Unknown'),
                        collection_name=collection_name,
                        metadata=meta_dict
                    ))

                logger.info(f"✅ Found {len(search_results[0])} results in {scope_label}")

            except Exception as e:
                logger.error(f"❌ Search failed in {collection.name}: {e}")
                continue

        # 4. Sort by score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[:request.top_k]

        # 5. Generate answer with LLM
        generated_answer = None
        tokens_used = 0

        if all_results:
            # Get options (use defaults if not provided)
            options = request.options or QueryOptions()

            logger.info(f"🤖 Generating answer with options: tone={options.tone}, lang={options.lang}, citations={options.citations}")

            # Generate answer using LLM
            generated_answer, tokens_used = _generate_collection_answer(
                results=all_results,
                question=request.question,
                options=options
            )

            logger.info(f"✅ Answer generated: {len(generated_answer)} chars, {tokens_used} tokens")

        processing_time = time.time() - start_time
        logger.info(f"✅ Collection query completed in {processing_time:.2f}s - {len(all_results)} results")

        return CollectionQueryResponse(
            results=all_results,
            generated_answer=generated_answer,
            success=True,
            processing_time=processing_time,
            collections_searched=len(collections_to_search),
            total_results=len(all_results),
            options_used=options
        )

    except Exception as e:
        logger.error(f"❌ Collection query error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Collection query failed: {str(e)}"
        )
