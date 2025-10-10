"""Milvus search handler for PRIVATE and SHARED scopes"""

import time
import json
from typing import List, Optional
from fastapi import HTTPException

from app.core.orchestrator.handlers.base import BaseHandler, HandlerResult, SearchResult, SourceType
from app.core.orchestrator.prompts import PromptTemplate
from schemas.api.requests.scope import DataScope, ScopeIdentifier
from schemas.api.requests.query import CollectionFilter
from api.core.milvus_manager import milvus_manager
from api.core.embeddings import embedding_service
from app.core.auth import UserContext


class MilvusSearchHandler(BaseHandler):
    """Handler for searching in Milvus collections (PRIVATE and SHARED)"""

    def __init__(self, user: UserContext, scopes: List[DataScope], collection_filters: Optional[List[CollectionFilter]] = None, options=None):
        """
        Initialize Milvus handler

        Args:
            user: User context with permissions
            scopes: List of scopes to search (PRIVATE, SHARED, or both)
            collection_filters: Optional list of collection filters with scope specification (None = no collections searched)
            options: Query options for tone, citations, etc.
        """
        # Use the first scope as source_type (or "private" if multiple)
        source_type = SourceType.PRIVATE if DataScope.PRIVATE in scopes else SourceType.SHARED

        # Get appropriate prompt based on scope
        if DataScope.PRIVATE in scopes:
            system_prompt = PromptTemplate.PRIVATE_SCOPE
        elif DataScope.SHARED in scopes:
            system_prompt = PromptTemplate.SHARED_SCOPE
        else:
            system_prompt = PromptTemplate.PRIVATE_SCOPE  # Default

        super().__init__(source_type, system_prompt=system_prompt, options=options)

        self.user = user
        self.scopes = scopes
        self.collection_filters = collection_filters  # Scope-aware collection filters
        self.collections = []

    async def search(
        self,
        question: str,
        top_k: int = 5,
        min_relevance_score: float = 0.7,
        **kwargs
    ) -> HandlerResult:
        """
        Search in Milvus collections

        Args:
            question: User's question
            top_k: Maximum number of results
            min_relevance_score: Minimum score threshold

        Returns:
            HandlerResult with search results from Milvus
        """
        start_time = time.time()

        try:
            # 1. Get target collections
            self._get_target_collections()

            if not self.collections:
                self.logger.warning(f"No accessible Milvus collections for user {self.user.user_id}")
                return self._create_success_result([], processing_time=time.time() - start_time)

            # 2. Generate query embedding
            self.logger.info(f"Generating embedding for question...")
            query_embedding = embedding_service.generate_embedding(question)

            # 3. Search across all collections
            all_results = []
            for collection_info in self.collections:
                collection = collection_info["collection"]
                scope_label = collection_info["scope_label"]

                self.logger.info(f"🔎 Searching in {collection.name} ({scope_label})")

                try:
                    search_results = collection.search(
                        [query_embedding],
                        'embedding',
                        {'metric_type': 'COSINE'},
                        limit=top_k,
                        expr=None,
                        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
                    )

                    # Convert Milvus results to SearchResult objects
                    for result in search_results[0]:
                        search_result = self._convert_milvus_result(result, scope_label)
                        if search_result:
                            all_results.append(search_result)

                    self.logger.info(f"✅ Found {len(search_results[0])} results in {scope_label}")

                except Exception as e:
                    self.logger.error(f"❌ Search failed in {collection.name}: {e}")
                    continue

            # 4. Sort by score and limit
            all_results.sort(key=lambda x: x.score, reverse=True)
            all_results = all_results[:top_k]

            # 5. Generate answer using scope-specific prompt
            generated_answer = None
            if all_results:
                generated_answer = await self._generate_answer(
                    question=question,
                    search_results=all_results,
                    max_sources=5
                )

            processing_time = time.time() - start_time
            return self._create_success_result(
                all_results,
                processing_time=processing_time,
                generated_answer=generated_answer
            )

        except Exception as e:
            self.logger.error(f"Milvus handler error: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_error_result(str(e))

    def _get_target_collections(self):
        """
        Get Milvus collections based on collection filters and user permissions

        NEW BEHAVIOR:
        - If collection_filters is None → Search DEFAULT SPACES (backward compatible)
        - If collection_filters is specified → Search NAMED COLLECTIONS
        - Example: {"name": "sozlesmeler", "scopes": ["private", "shared"]}
          → Searches both user_id_col_sozlesmeler_chunks_1536 AND org_id_col_sozlesmeler_chunks_1536
        """
        # Case 1: No collection filters → Search DEFAULT SPACES
        if not self.collection_filters:
            self.logger.info("📦 Collection filters yok - DEFAULT space'lerde arama yapılacak")

            for scope in self.scopes:
                if scope == DataScope.PRIVATE:
                    if not self.user.data_access.own_data:
                        self.logger.warning(f"❌ User {self.user.user_id} doesn't have own_data access")
                        continue

                    private_scope = ScopeIdentifier(
                        organization_id=self.user.organization_id,
                        scope_type=DataScope.PRIVATE,
                        user_id=self.user.user_id,
                        collection_name=None  # Default space
                    )

                    try:
                        collection = milvus_manager.get_collection(private_scope, auto_create=False)
                        self.collections.append({
                            "collection": collection,
                            "scope_label": "private"
                        })
                        self.logger.info(f"✅ Private DEFAULT space bulundu: {collection.name}")
                    except Exception as e:
                        self.logger.warning(f"⚠️ Private default space bulunamadı: {e}")

                elif scope == DataScope.SHARED:
                    if not self.user.data_access.shared_data:
                        self.logger.warning(f"❌ User {self.user.user_id} doesn't have shared_data access")
                        continue

                    shared_scope = ScopeIdentifier(
                        organization_id=self.user.organization_id,
                        scope_type=DataScope.SHARED,
                        collection_name=None  # Default space
                    )

                    try:
                        collection = milvus_manager.get_collection(shared_scope, auto_create=False)
                        self.collections.append({
                            "collection": collection,
                            "scope_label": "shared"
                        })
                        self.logger.info(f"✅ Shared DEFAULT space bulundu: {collection.name}")
                    except Exception as e:
                        self.logger.warning(f"⚠️ Shared default space bulunamadı: {e}")

            self.logger.info(f"📊 Toplam {len(self.collections)} default space'te arama yapılacak")
            return

        # Case 2: Collection filters specified → Search NAMED COLLECTIONS
        self.logger.info(f"🔍 {len(self.collection_filters)} adet koleksiyon işleniyor")

        # Process each collection filter
        for collection_filter in self.collection_filters:
            collection_name = collection_filter.name
            filter_scopes = collection_filter.scopes

            self.logger.info(f"📦 '{collection_name}' koleksiyonu - aranacak scope'lar: {[s.value for s in filter_scopes]}")

            # Search in each scope specified by the filter
            for scope in filter_scopes:
                if scope == DataScope.PRIVATE:
                    # Check access permission
                    if not self.user.data_access.own_data:
                        self.logger.warning(f"❌ User {self.user.user_id} doesn't have own_data access - skipping private/{collection_name}")
                        continue

                    # Create scope identifier for private collection
                    private_scope = ScopeIdentifier(
                        organization_id=self.user.organization_id,
                        scope_type=DataScope.PRIVATE,
                        user_id=self.user.user_id,
                        collection_name=collection_name
                    )

                    try:
                        collection = milvus_manager.get_collection(private_scope, auto_create=False)
                        self.collections.append({
                            "collection": collection,
                            "scope_label": f"private/{collection_name}"
                        })
                        self.logger.info(f"✅ '{collection_name}' private koleksiyonu bulundu ve aranacak: {collection.name}")
                    except Exception as e:
                        error_msg = f"'{collection_name}' private koleksiyonu bulunamadı"
                        if "does not exist" in str(e).lower() or "not exist" in str(e).lower():
                            self.logger.warning(f"⚠️ {error_msg} (koleksiyon oluşturulmamış olabilir)")
                        else:
                            self.logger.warning(f"⚠️ {error_msg}: {str(e)}")

                elif scope == DataScope.SHARED:
                    # Check access permission
                    if not self.user.data_access.shared_data:
                        self.logger.warning(f"❌ User {self.user.user_id} doesn't have shared_data access - skipping shared/{collection_name}")
                        continue

                    # Create scope identifier for shared collection
                    shared_scope = ScopeIdentifier(
                        organization_id=self.user.organization_id,
                        scope_type=DataScope.SHARED,
                        collection_name=collection_name
                    )

                    try:
                        collection = milvus_manager.get_collection(shared_scope, auto_create=False)
                        self.collections.append({
                            "collection": collection,
                            "scope_label": f"shared/{collection_name}"
                        })
                        self.logger.info(f"✅ '{collection_name}' shared koleksiyonu bulundu ve aranacak: {collection.name}")
                    except Exception as e:
                        error_msg = f"'{collection_name}' shared koleksiyonu bulunamadı"
                        if "does not exist" in str(e).lower() or "not exist" in str(e).lower():
                            self.logger.warning(f"⚠️ {error_msg} (koleksiyon oluşturulmamış olabilir)")
                        else:
                            self.logger.warning(f"⚠️ {error_msg}: {str(e)}")

        self.logger.info(f"📊 Toplam {len(self.collections)} koleksiyonda arama yapılacak")

    def _convert_milvus_result(self, result, scope_label: str) -> SearchResult:
        """Convert Milvus search result to SearchResult object"""
        try:
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

            # Determine source type
            source_type = SourceType.PRIVATE if scope_label == "private" else SourceType.SHARED

            return SearchResult(
                score=score,
                document_id=doc_id,
                text=text,
                source_type=source_type,
                metadata=meta_dict,
                chunk_index=chunk_index,
                page_number=meta_dict.get('page_number', 0),
                document_title=meta_dict.get('document_title', 'Unknown'),
                created_at=meta_dict.get('created_at', 0)
            )

        except Exception as e:
            self.logger.error(f"Error converting Milvus result: {e}")
            return None
