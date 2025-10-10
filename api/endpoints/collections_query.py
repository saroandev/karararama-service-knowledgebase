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
from schemas.api.responses.collection import CollectionQueryResponse, CollectionSearchResult
from api.core.milvus_manager import milvus_manager
from api.core.embeddings import embedding_service
from app.core.auth import UserContext, get_current_user
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


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
                        error_msg = f"'{collection_name}' private collection not found"
                        if "does not exist" in str(e).lower() or "not exist" in str(e).lower():
                            logger.warning(f"⚠️ {error_msg} (may not be created yet)")
                        else:
                            logger.warning(f"⚠️ {error_msg}: {str(e)}")

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
                        error_msg = f"'{collection_name}' shared collection not found"
                        if "does not exist" in str(e).lower() or "not exist" in str(e).lower():
                            logger.warning(f"⚠️ {error_msg} (may not be created yet)")
                        else:
                            logger.warning(f"⚠️ {error_msg}: {str(e)}")

        if not collections_to_search:
            logger.warning(f"No accessible collections found for user {user.user_id}")
            processing_time = time.time() - start_time
            return CollectionQueryResponse(
                results=[],
                generated_answer=None,
                success=True,
                processing_time=processing_time,
                collections_searched=0,
                total_results=0
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

        # 5. Generate answer (optional - based on options)
        generated_answer = None
        if all_results and request.options:
            # TODO: Implement answer generation using options (tone, lang, citations)
            # For now, skip answer generation to keep endpoint simple
            pass

        processing_time = time.time() - start_time
        logger.info(f"✅ Collection query completed in {processing_time:.2f}s - {len(all_results)} results")

        return CollectionQueryResponse(
            results=all_results,
            generated_answer=generated_answer,
            success=True,
            processing_time=processing_time,
            collections_searched=len(collections_to_search),
            total_results=len(all_results)
        )

    except Exception as e:
        logger.error(f"❌ Collection query error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Collection query failed: {str(e)}"
        )
