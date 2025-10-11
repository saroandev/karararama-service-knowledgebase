"""
Indexing stage for document processing pipeline

This stage inserts chunks and embeddings into Milvus vector database.
"""
import datetime
from typing import List, Dict, Any

from app.core.orchestrator.stages.base import PipelineStage, StageResult
from app.core.orchestrator.pipeline_context import PipelineContext
from api.core.milvus_manager import milvus_manager
from app.config import settings


class IndexingStage(PipelineStage):
    """
    Stage 5: Milvus Indexing

    Inserts chunks and embeddings into Milvus vector database:
    - Prepares data in Milvus schema format
    - Generates unique IDs for chunks
    - Creates comprehensive metadata
    - Performs batch insert
    - Loads collection for immediate search

    Input (from context):
        - chunks: List[SimpleChunk]
        - embeddings: List[np.ndarray]
        - document_id: str
        - scope_identifier: ScopeIdentifier
        - user: UserContext
        - validation_result: ValidationResult

    Output (to context):
        - milvus_insert_result: Dict with insert statistics
    """

    @property
    def name(self) -> str:
        return "indexing"

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute indexing stage

        Args:
            context: Pipeline context with chunks, embeddings, and metadata

        Returns:
            StageResult indicating indexing success/failure
        """
        self.logger.info(f"🗄️  Indexing {len(context.chunks) if context.chunks else 0} chunks to Milvus")

        # Validate input
        error = self.validate_input(context, 'chunks', 'embeddings', 'document_id', 'scope_identifier', 'user')
        if error:
            return StageResult(
                success=False,
                stage_name=self.name,
                error=error
            )

        # Validate chunks and embeddings match
        if len(context.chunks) != len(context.embeddings):
            return StageResult(
                success=False,
                stage_name=self.name,
                error=f"Chunks and embeddings count mismatch: {len(context.chunks)} chunks vs {len(context.embeddings)} embeddings"
            )

        try:
            # Get scope-aware Milvus collection
            collection = milvus_manager.get_collection(context.scope_identifier)
            collection_name = context.get_collection_name()

            self.logger.info(f"📦 Target collection: {collection_name}")

            # Prepare Milvus data arrays
            milvus_data = self._prepare_milvus_data(context)

            # Log data preparation
            self.logger.info(f"📝 Prepared data for Milvus:")
            self.logger.info(f"   IDs: {len(milvus_data['ids'])}")
            self.logger.info(f"   Document IDs: {len(milvus_data['document_ids'])}")
            self.logger.info(f"   Chunk Indices: {len(milvus_data['chunk_indices'])}")
            self.logger.info(f"   Texts: {len(milvus_data['texts'])}")
            self.logger.info(f"   Embeddings: {len(milvus_data['embeddings'])}")
            self.logger.info(f"   Metadata: {len(milvus_data['metadata'])}")

            # Insert data into Milvus
            # Data order must match schema: id, document_id, chunk_index, chunk_text, embedding, metadata
            data = [
                milvus_data['ids'],
                milvus_data['document_ids'],
                milvus_data['chunk_indices'],
                milvus_data['texts'],
                milvus_data['embeddings'],
                milvus_data['metadata']
            ]

            self.logger.info(f"💾 Inserting {len(context.chunks)} chunks into Milvus...")
            insert_result = collection.insert(data)

            # Load collection for immediate search
            self.logger.info(f"🔄 Loading collection for immediate search...")
            collection.load()

            # Store insert result in context
            context.milvus_insert_result = {
                'insert_count': insert_result.insert_count if hasattr(insert_result, 'insert_count') else len(context.chunks),
                'collection_name': collection_name,
                'ids': milvus_data['ids']
            }

            # Log insert statistics
            self._log_insert_stats(context, milvus_data)

            # Update context stats
            context.stats['milvus_insert_count'] = len(context.chunks)
            context.stats['milvus_collection'] = collection_name

            # Success
            return StageResult(
                success=True,
                stage_name=self.name,
                message=f"✅ Indexed {len(context.chunks)} chunks to Milvus collection '{collection_name}'",
                metadata={
                    "insert_count": len(context.chunks),
                    "collection_name": collection_name,
                    "embedding_dimension": len(milvus_data['embeddings'][0]) if milvus_data['embeddings'] else 0
                }
            )

        except Exception as e:
            self.logger.exception(f"Milvus indexing error: {e}")

            # Check for common Milvus errors
            error_msg = str(e).lower()
            if "connection" in error_msg:
                error_detail = "Failed to connect to Milvus database. Check MILVUS_HOST and MILVUS_PORT."
            elif "collection" in error_msg and "not exist" in error_msg:
                error_detail = f"Collection '{context.get_collection_name()}' does not exist in Milvus."
            elif "schema" in error_msg or "field" in error_msg:
                error_detail = "Data format mismatch with Milvus schema. Check field types and order."
            else:
                error_detail = f"Failed to index chunks: {str(e)}"

            return StageResult(
                success=False,
                stage_name=self.name,
                error=error_detail,
                metadata={
                    "exception_type": type(e).__name__,
                    "chunks_attempted": len(context.chunks)
                }
            )

    async def rollback(self, context: PipelineContext) -> None:
        """
        Rollback Milvus insertion by deleting inserted chunks

        This is called if later stages fail, to maintain consistency.
        """
        if not context.milvus_insert_result:
            self.logger.info(f"[{self.name}] No Milvus insert to rollback")
            return

        try:
            # Get collection
            collection = milvus_manager.get_collection(context.scope_identifier)

            # Delete by document_id (deletes all chunks of this document)
            expr = f'document_id == "{context.document_id}"'
            self.logger.warning(f"🔄 Rolling back Milvus insert: deleting document {context.document_id}")

            collection.delete(expr)
            collection.load()  # Reload after deletion

            self.logger.info(f"✅ Rolled back Milvus insertion for document {context.document_id}")

        except Exception as e:
            self.logger.error(f"❌ Failed to rollback Milvus insertion: {e}")
            # Don't raise - rollback is best effort

    def _prepare_milvus_data(self, context: PipelineContext) -> Dict[str, List]:
        """
        Prepare data arrays for Milvus insertion

        Args:
            context: Pipeline context with all required data

        Returns:
            Dictionary with data arrays matching Milvus schema
        """
        current_time = datetime.datetime.now()
        document_title = context.filename.replace('.pdf', '')

        # Extract document title from validation metadata if available
        if context.validation_result and context.validation_result.metadata:
            if context.validation_result.metadata.title:
                document_title = context.validation_result.metadata.title

        # Extract file hash from validation
        file_hash = context.validation_result.file_hash if context.validation_result else ""

        # Calculate document size
        document_size_bytes = len(context.file_data) if context.file_data else 0

        # Prepare arrays
        ids = []
        document_ids = []
        chunk_indices = []
        texts = []
        embeddings_list = []
        metadata_list = []

        for i, chunk in enumerate(context.chunks):
            # Generate unique ID
            chunk_id = f"{context.document_id}_{i:04d}"
            ids.append(chunk_id)

            # Document ID (same for all chunks)
            document_ids.append(context.document_id)

            # Chunk index
            chunk_indices.append(i)

            # Chunk text
            texts.append(chunk.text)

            # Embedding (convert numpy array to list for Milvus)
            embedding = context.embeddings[i]
            if hasattr(embedding, 'tolist'):
                embeddings_list.append(embedding.tolist())
            else:
                embeddings_list.append(list(embedding))

            # Comprehensive metadata
            metadata = {
                "chunk_id": chunk.chunk_id,
                "page_number": chunk.page_number,
                "minio_object_path": f"{context.document_id}/{chunk.chunk_id}.json",
                "document_title": document_title,
                "file_hash": file_hash,
                "created_at": int(current_time.timestamp() * 1000),
                "document_size_bytes": document_size_bytes,
                "embedding_model": settings.EMBEDDING_MODEL,
                "embedding_dimension": len(embeddings_list[i]),
                "embedding_size_bytes": len(embeddings_list[i]) * 4,  # float32 = 4 bytes
                # Multi-tenant metadata
                "organization_id": context.user.organization_id,
                "user_id": context.user.user_id if context.scope_identifier.scope_type.value == "private" else None,
                "scope_type": context.scope_identifier.scope_type.value,
                "uploaded_by": context.user.user_id,
                "uploaded_by_email": context.user.email
            }

            # Add validation metadata if available
            if context.validation_result:
                metadata["document_type"] = context.validation_result.document_type
                # Extract status safely (might be string or enum)
                status_value = context.validation_result.status.value if hasattr(context.validation_result.status, 'value') else context.validation_result.status
                metadata["validation_status"] = status_value

            # Add collection name if using named collection
            if context.scope_identifier.collection_name:
                metadata["collection_name"] = context.scope_identifier.collection_name

            metadata_list.append(metadata)

        return {
            'ids': ids,
            'document_ids': document_ids,
            'chunk_indices': chunk_indices,
            'texts': texts,
            'embeddings': embeddings_list,
            'metadata': metadata_list
        }

    def _log_insert_stats(self, context: PipelineContext, milvus_data: Dict) -> None:
        """
        Log detailed insert statistics

        Args:
            context: Pipeline context
            milvus_data: Prepared Milvus data
        """
        self.logger.info(f"📊 Milvus Insert Statistics:")
        self.logger.info(f"   Collection: {context.get_collection_name()}")
        self.logger.info(f"   Document ID: {context.document_id}")
        self.logger.info(f"   Chunks Inserted: {len(milvus_data['ids'])}")
        self.logger.info(f"   Embedding Dimension: {len(milvus_data['embeddings'][0]) if milvus_data['embeddings'] else 0}")
        self.logger.info(f"   Scope: {context.scope_identifier.scope_type.value}")

        if context.scope_identifier.collection_name:
            self.logger.info(f"   Collection Name: {context.scope_identifier.collection_name}")

        # Memory usage
        total_embeddings_mb = sum(len(emb) * 4 for emb in milvus_data['embeddings']) / (1024 * 1024)
        self.logger.info(f"   Embeddings Size: {total_embeddings_mb:.2f} MB")
