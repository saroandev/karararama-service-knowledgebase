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

from schemas.api.requests.collection import CollectionQueryRequest, SearchMode
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from schemas.api.requests.query import QueryOptions
from schemas.api.responses.collection import CollectionQueryResponse, CollectionSearchResult
from api.core.milvus_client_manager import milvus_client_manager  # NEW: MilvusClient API
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

        # 2. Get target collections (using MilvusClient API)
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
                        # Use MilvusClientManager to check and get collection name
                        milvus_collection_name = milvus_client_manager.get_or_create_collection(
                            private_scope,
                            auto_create=False
                        )
                        collections_to_search.append({
                            "collection_name_milvus": milvus_collection_name,
                            "scope_label": f"private/{collection_name}",
                            "collection_name": collection_name
                        })
                        logger.info(f"✅ '{collection_name}' private collection found: {milvus_collection_name}")
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
                        # Use MilvusClientManager to check and get collection name
                        milvus_collection_name = milvus_client_manager.get_or_create_collection(
                            shared_scope,
                            auto_create=False
                        )
                        collections_to_search.append({
                            "collection_name_milvus": milvus_collection_name,
                            "scope_label": f"shared/{collection_name}",
                            "collection_name": collection_name
                        })
                        logger.info(f"✅ '{collection_name}' shared collection found: {milvus_collection_name}")
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

        # 3. Search across all collections based on search_mode
        all_results = []
        client = milvus_client_manager.get_client()

        # Log search mode
        mode_name = {
            SearchMode.HYBRID: "Hybrid Search (Semantic + BM25)",
            SearchMode.SEMANTIC: "Semantic Search Only (Dense Vector)",
            SearchMode.BM25: "BM25 Search Only (Keyword)"
        }.get(request.search_mode, "Hybrid Search")

        logger.info(f"🔍 SEARCH MODE: {mode_name}")
        logger.info(f"📊 Search Parameters:")

        if request.search_mode in [SearchMode.HYBRID, SearchMode.SEMANTIC]:
            logger.info(f"   • Dense Field: embedding (1536-dim, COSINE)")
        if request.search_mode in [SearchMode.HYBRID, SearchMode.BM25]:
            logger.info(f"   • Sparse Field: sparse (BM25 keyword)")
        if request.search_mode == SearchMode.HYBRID:
            logger.info(f"   • Ranker: RRF (Reciprocal Rank Fusion)")
        logger.info(f"   • Top-K: {request.top_k}")

        for collection_info in collections_to_search:
            milvus_collection_name = collection_info["collection_name_milvus"]
            scope_label = collection_info["scope_label"]
            collection_name = collection_info["collection_name"]

            logger.info(f"\n🔎 Searching in {milvus_collection_name} ({scope_label})")

            try:
                search_start = time.time()

                # ========================================
                # CONDITIONAL SEARCH BASED ON MODE
                # ========================================

                if request.search_mode == SearchMode.SEMANTIC:
                    # ===== SEMANTIC ONLY MODE =====
                    logger.info(f"   🧠 Semantic search (dense vector only)...")
                    dense_start = time.time()
                    semantic_results = client.search(
                        collection_name=milvus_collection_name,
                        data=[query_embedding],
                        anns_field='embedding',
                        limit=request.top_k,
                        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
                    )
                    dense_time = time.time() - dense_start
                    logger.info(f"      ⏱️  Found {len(semantic_results[0])} results in {dense_time:.3f}s")

                    # Process semantic results
                    for rank, result in enumerate(semantic_results[0], 1):
                        entity = result.get('entity', {})
                        doc_id = entity.get('document_id', 'unknown')
                        chunk_index = entity.get('chunk_index', 0)
                        text = entity.get('text', '')
                        metadata = entity.get('metadata', {})
                        distance = result.get('distance', 0)

                        # COSINE metric in Milvus: distance = 1 - cosine_similarity
                        # Lower distance = higher similarity
                        # Convert to similarity: 1 - distance
                        similarity = 1 - distance

                        # Parse metadata
                        if isinstance(metadata, str):
                            meta_dict = json.loads(metadata)
                        else:
                            meta_dict = metadata if metadata else {}

                        # Determine source type
                        source_type = "private" if "private" in scope_label else "shared"

                        # Normalize to 0-100 range
                        final_score = similarity * 100

                        # Detailed logging
                        logger.info(f"   {rank}. 📄 {meta_dict.get('document_title', 'Unknown')[:50]}")
                        logger.info(f"      🧠 Semantic Score: {similarity:.4f} → {final_score:.1f}/100")
                        logger.info(f"      📍 Document: {doc_id}, Chunk: {chunk_index}")

                        all_results.append(CollectionSearchResult(
                            score=final_score,  # 0-100 range
                            document_id=doc_id,
                            text=text,
                            source_type=source_type,
                            chunk_index=chunk_index,
                            page_number=meta_dict.get('page_number', 0),
                            document_title=meta_dict.get('document_title', 'Unknown'),
                            collection_name=collection_name,
                            metadata=meta_dict
                        ))

                    search_time = time.time() - search_start
                    logger.info(f"   ✅ Semantic search completed in {search_time:.3f}s: {len(semantic_results[0])} results")

                elif request.search_mode == SearchMode.BM25:
                    # ===== BM25 ONLY MODE =====
                    logger.info(f"   🔤 BM25 search (keyword only)...")
                    bm25_start = time.time()
                    bm25_results = client.search(
                        collection_name=milvus_collection_name,
                        data=[request.question],  # Text query
                        anns_field='sparse',
                        limit=request.top_k,
                        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
                    )
                    bm25_time = time.time() - bm25_start
                    logger.info(f"      ⏱️  Found {len(bm25_results[0])} results in {bm25_time:.3f}s")

                    # Find max BM25 score for normalization
                    max_bm25 = max([r.get('distance', 0) for r in bm25_results[0]], default=1.0)
                    if max_bm25 == 0:
                        max_bm25 = 1.0

                    # Process BM25 results
                    for rank, result in enumerate(bm25_results[0], 1):
                        entity = result.get('entity', {})
                        doc_id = entity.get('document_id', 'unknown')
                        chunk_index = entity.get('chunk_index', 0)
                        text = entity.get('text', '')
                        metadata = entity.get('metadata', {})
                        bm25_score = result.get('distance', 0)

                        # Parse metadata
                        if isinstance(metadata, str):
                            meta_dict = json.loads(metadata)
                        else:
                            meta_dict = metadata if metadata else {}

                        # Determine source type
                        source_type = "private" if "private" in scope_label else "shared"

                        # Normalize to 0-100 range
                        final_score = (bm25_score / max_bm25) * 100

                        # Detailed logging
                        logger.info(f"   {rank}. 📄 {meta_dict.get('document_title', 'Unknown')[:50]}")
                        logger.info(f"      🔤 BM25 Score: {bm25_score:.4f} → {final_score:.1f}/100")
                        logger.info(f"      📍 Document: {doc_id}, Chunk: {chunk_index}")

                        all_results.append(CollectionSearchResult(
                            score=final_score,  # 0-100 range
                            document_id=doc_id,
                            text=text,
                            source_type=source_type,
                            chunk_index=chunk_index,
                            page_number=meta_dict.get('page_number', 0),
                            document_title=meta_dict.get('document_title', 'Unknown'),
                            collection_name=collection_name,
                            metadata=meta_dict
                        ))

                    search_time = time.time() - search_start
                    logger.info(f"   ✅ BM25 search completed in {search_time:.3f}s: {len(bm25_results[0])} results")

                else:  # SearchMode.HYBRID (default)
                    # ===== HYBRID MODE (Semantic + BM25 with RRF) =====

                    # 1. Dense vector search (Semantic)
                    logger.info(f"   🧠 Dense search (semantic)...")
                    dense_start = time.time()
                    dense_results = client.search(
                        collection_name=milvus_collection_name,
                        data=[query_embedding],
                        anns_field='embedding',
                        limit=request.top_k * 2,
                        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
                    )
                    dense_time = time.time() - dense_start
                    logger.info(f"      ⏱️  Found {len(dense_results[0])} results in {dense_time:.3f}s")

                    # 2. BM25 search (Keyword)
                    logger.info(f"   🔤 BM25 search (keyword)...")
                    bm25_start = time.time()
                    bm25_results = client.search(
                        collection_name=milvus_collection_name,
                        data=[request.question],  # Text query
                        anns_field='sparse',
                        limit=request.top_k * 2,
                        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
                    )
                    bm25_time = time.time() - bm25_start
                    logger.info(f"      ⏱️  Found {len(bm25_results[0])} results in {bm25_time:.3f}s")

                    # 3. Manual RRF Fusion with score tracking
                    logger.info(f"   🔀 Fusing results with RRF...")

                    # Build score dictionaries: {(doc_id, chunk_index): (score, rank)}
                    semantic_scores = {}
                    for rank, result in enumerate(dense_results[0], 1):
                        entity = result.get('entity', {})
                        doc_id = entity.get('document_id', 'unknown')
                        chunk_idx = entity.get('chunk_index', 0)
                        distance = result.get('distance', 0)
                        # COSINE distance: convert to similarity (1 - distance)
                        similarity = 1 - distance
                        key = (doc_id, chunk_idx)
                        semantic_scores[key] = {'score': similarity, 'rank': rank, 'result': result}

                    bm25_scores = {}
                    for rank, result in enumerate(bm25_results[0], 1):
                        entity = result.get('entity', {})
                        doc_id = entity.get('document_id', 'unknown')
                        chunk_idx = entity.get('chunk_index', 0)
                        distance = result.get('distance', 0)
                        # BM25 score is in distance field (higher = better)
                        key = (doc_id, chunk_idx)
                        bm25_scores[key] = {'score': distance, 'rank': rank, 'result': result}

                    # Combine all unique documents
                    all_doc_keys = set(semantic_scores.keys()) | set(bm25_scores.keys())

                    # Calculate RRF scores
                    k = 60  # RRF constant
                    rrf_results = []

                    for doc_key in all_doc_keys:
                        sem_data = semantic_scores.get(doc_key, {'score': 0, 'rank': 9999, 'result': None})
                        bm25_data = bm25_scores.get(doc_key, {'score': 0, 'rank': 9999, 'result': None})

                        # RRF formula: sum of 1/(k + rank_i)
                        rrf_score = (1 / (k + sem_data['rank'])) + (1 / (k + bm25_data['rank']))

                        # Use result from whichever search found it (prefer semantic)
                        base_result = sem_data['result'] or bm25_data['result']
                        if base_result is None:
                            continue

                        rrf_results.append({
                            'doc_key': doc_key,
                            'semantic_score': sem_data['score'],
                            'semantic_rank': sem_data['rank'],
                            'bm25_score': bm25_data['score'],
                            'bm25_rank': bm25_data['rank'],
                            'rrf_score': rrf_score,
                            'result': base_result
                        })

                    # Sort by RRF score and limit
                    rrf_results.sort(key=lambda x: x['rrf_score'], reverse=True)
                    rrf_results = rrf_results[:request.top_k]

                    # Calculate max RRF for normalization to 0-100
                    max_rrf = (1 / (k + 1)) + (1 / (k + 1))  # Both rank 1

                    search_time = time.time() - search_start
                    logger.info(f"   ⏱️  Hybrid search completed in {search_time:.3f}s")
                    logger.info(f"   📈 Fused results: {len(rrf_results)}")

                    # Convert fused results to CollectionSearchResult objects with detailed logging
                    for idx, rrf_item in enumerate(rrf_results, 1):
                        base_result = rrf_item['result']
                        entity = base_result.get('entity', {})

                        doc_id = entity.get('document_id', 'unknown')
                        chunk_index = entity.get('chunk_index', 0)
                        text = entity.get('text', '')
                        metadata = entity.get('metadata', {})

                        # Parse metadata
                        if isinstance(metadata, str):
                            meta_dict = json.loads(metadata)
                        else:
                            meta_dict = metadata if metadata else {}

                        # Determine source type
                        source_type = "private" if "private" in scope_label else "shared"

                        # Extract scores
                        semantic_score = rrf_item['semantic_score']
                        semantic_rank = rrf_item['semantic_rank']
                        bm25_score = rrf_item['bm25_score']
                        bm25_rank = rrf_item['bm25_rank']
                        rrf_score = rrf_item['rrf_score']

                        # Normalize RRF score to 0-100 range
                        final_score = (rrf_score / max_rrf) * 100

                        # Determine which search method found it
                        in_semantic = semantic_rank < 9999
                        in_bm25 = bm25_rank < 9999
                        match_type = ""
                        if in_semantic and in_bm25:
                            match_type = "📊 BOTH searches!"
                        elif in_semantic:
                            match_type = "🧠 Semantic only"
                        elif in_bm25:
                            match_type = "🔤 BM25 only"

                        # Detailed logging
                        logger.info(f"   {idx}. 📄 {meta_dict.get('document_title', 'Unknown')[:50]}")
                        if in_semantic:
                            logger.info(f"      🧠 Semantic: {semantic_score:.4f} (rank: {semantic_rank})")
                        else:
                            logger.info(f"      🧠 Semantic: - (not found)")

                        if in_bm25:
                            logger.info(f"      🔤 BM25: {bm25_score:.4f} (rank: {bm25_rank})")
                        else:
                            logger.info(f"      🔤 BM25: - (not found)")

                        logger.info(f"      🔀 RRF: {rrf_score:.4f} → {final_score:.1f}/100")
                        logger.info(f"      {match_type}")
                        logger.info(f"      📍 Document: {doc_id}, Chunk: {chunk_index}")

                        all_results.append(CollectionSearchResult(
                            score=final_score,  # 0-100 range
                            document_id=doc_id,
                            text=text,
                            source_type=source_type,
                            chunk_index=chunk_index,
                            page_number=meta_dict.get('page_number', 0),
                            document_title=meta_dict.get('document_title', 'Unknown'),
                            collection_name=collection_name,
                            metadata=meta_dict
                        ))

                    logger.info(f"   ✅ Hybrid search completed in {scope_label}: {len(rrf_results)} results")

            except Exception as e:
                logger.error(f"❌ Search failed in {milvus_collection_name}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                continue

        # 4. Sort by score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[:request.top_k]

        # Log final ranking with 0-100 scores
        logger.info(f"\n📊 FINAL RANKING (Top {len(all_results)} results after merge & sort):")
        for idx, result in enumerate(all_results, 1):
            # Score is now in 0-100 range
            logger.info(f"   {idx}. Score: {result.score:.1f}/100 | {result.document_title[:40]}... (chunk {result.chunk_index})")

        # 5. Generate answer with LLM
        generated_answer = None
        tokens_used = 0

        if all_results:
            # Get options (use defaults if not provided)
            options = request.options or QueryOptions()

            logger.info(f"\n🤖 Generating answer with LLM:")
            logger.info(f"   • Model: {settings.OPENAI_MODEL}")
            logger.info(f"   • Tone: {options.tone}")
            logger.info(f"   • Language: {options.lang}")
            logger.info(f"   • Citations: {options.citations}")
            logger.info(f"   • Context chunks: {len(all_results)}")

            # Generate answer using LLM
            generated_answer, tokens_used = _generate_collection_answer(
                results=all_results,
                question=request.question,
                options=options
            )

            logger.info(f"✅ Answer generated:")
            logger.info(f"   • Length: {len(generated_answer)} chars")
            logger.info(f"   • Tokens used: {tokens_used}")
            logger.info(f"   • Preview: {generated_answer[:150]}...")

        processing_time = time.time() - start_time

        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ QUERY COMPLETED SUCCESSFULLY")
        logger.info(f"{'=' * 60}")
        logger.info(f"📈 Statistics:")
        logger.info(f"   • Total processing time: {processing_time:.3f}s")
        logger.info(f"   • Collections searched: {len(collections_to_search)}")
        logger.info(f"   • Results returned: {len(all_results)}")
        logger.info(f"   • Search method: {mode_name}")
        if request.search_mode == SearchMode.HYBRID:
            logger.info(f"   • Ranker: RRF (Reciprocal Rank Fusion)")
        logger.info(f"   • Answer generated: {'Yes' if generated_answer else 'No'}")
        logger.info(f"{'=' * 60}\n")

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
