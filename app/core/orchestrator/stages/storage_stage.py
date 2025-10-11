"""
Storage stage for document processing pipeline

This stage stores PDF documents and chunks in MinIO object storage.
"""
from typing import Dict

from app.core.orchestrator.stages.base import PipelineStage, StageResult
from app.core.orchestrator.pipeline_context import PipelineContext
from app.core.storage import storage


class StorageStage(PipelineStage):
    """
    Stage 6: MinIO Storage (OPTIONAL - NON-BLOCKING)

    Stores documents and chunks in MinIO object storage:
    - Uploads original PDF to scope-aware bucket (optional)
    - Uploads chunks as JSON files
    - Creates comprehensive metadata
    - Uses scope-aware paths for multi-tenant isolation

    **IMPORTANT**: This stage is non-blocking and optional.
    - If PDF upload fails (e.g., deadlock), stage continues with success
    - Document data is already in Milvus (critical) before this stage
    - MinIO is for storage/backup only, not for search

    Input (from context):
        - file_data: bytes (original PDF)
        - filename: str
        - document_id: str
        - chunks: List[SimpleChunk]
        - scope_identifier: ScopeIdentifier
        - validation_result: ValidationResult

    Output (to context):
        - storage_paths: Dict with uploaded file paths
        - stats['pdf_uploaded']: bool (whether PDF uploaded successfully)
        - stats['chunks_uploaded']: int (number of chunks uploaded)
    """

    @property
    def name(self) -> str:
        return "storage"

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute storage stage

        Args:
            context: Pipeline context with file data and chunks

        Returns:
            StageResult indicating storage success/failure
        """
        self.logger.info(f"💾 Uploading document and chunks to MinIO")

        # Validate input
        error = self.validate_input(context, 'file_data', 'filename', 'document_id', 'chunks', 'scope_identifier')
        if error:
            return StageResult(
                success=False,
                stage_name=self.name,
                error=error
            )

        storage_paths = {}

        # Track what was uploaded successfully
        pdf_uploaded = False
        bucket = context.get_bucket_name()
        prefix = context.get_object_prefix("docs")

        try:
            # 1. Upload PDF document to MinIO (OPTIONAL - non-blocking)
            self.logger.info(f"📄 Uploading PDF: {context.filename} ({len(context.file_data)} bytes)")

            # Prepare document metadata
            document_metadata = self._prepare_document_metadata(context)

            # Try to upload PDF (may fail due to deadlock)
            try:
                pdf_uploaded = storage.upload_pdf_to_raw_documents(
                    document_id=context.document_id,
                    file_data=context.file_data,
                    filename=context.filename,
                    metadata=document_metadata,
                    scope=context.scope_identifier
                )

                if pdf_uploaded:
                    # Store PDF path
                    storage_paths['pdf'] = f"{bucket}/{prefix}{context.document_id}/file.pdf"
                    self.logger.info(f"✅ PDF uploaded successfully")
                else:
                    self.logger.warning(f"⚠️  PDF upload returned False, but continuing (Milvus has the data)")

            except Exception as pdf_error:
                # PDF upload failed (likely deadlock), but continue anyway
                self.logger.warning(f"⚠️  PDF upload failed: {pdf_error}")
                self.logger.warning(f"⚠️  Continuing without PDF in MinIO (data is in Milvus)")
                pdf_uploaded = False

            # 2. Upload chunks to MinIO
            self.logger.info(f"📦 Uploading {len(context.chunks)} chunks...")

            chunks_uploaded = 0
            for i, chunk in enumerate(context.chunks):
                try:
                    chunk_uploaded = storage.upload_chunk(
                        document_id=context.document_id,
                        chunk_id=chunk.chunk_id,
                        chunk_text=chunk.text,
                        metadata={
                            "page_number": chunk.page_number,
                            "chunk_index": chunk.chunk_index or i
                        },
                        scope=context.scope_identifier
                    )

                    if chunk_uploaded:
                        chunks_uploaded += 1
                    else:
                        self.logger.warning(f"⚠️  Failed to upload chunk {chunk.chunk_id}")

                except Exception as chunk_error:
                    self.logger.warning(f"⚠️  Error uploading chunk {chunk.chunk_id}: {chunk_error}")

            # Store chunks path
            chunks_prefix = context.get_object_prefix("chunks")
            storage_paths['chunks'] = f"{bucket}/{chunks_prefix}{context.document_id}/"

            self.logger.info(f"✅ Uploaded {chunks_uploaded}/{len(context.chunks)} chunks")

            # Check if all chunks uploaded successfully
            if chunks_uploaded < len(context.chunks):
                self.logger.warning(f"⚠️  Only {chunks_uploaded}/{len(context.chunks)} chunks uploaded successfully")
                # Don't fail - partial upload is acceptable

            # Store storage paths in context
            context.storage_paths = storage_paths

            # Log storage statistics
            self._log_storage_stats(context, storage_paths, chunks_uploaded, pdf_uploaded)

            # Update context stats
            context.stats['pdf_uploaded'] = pdf_uploaded
            context.stats['chunks_uploaded'] = chunks_uploaded
            context.stats['storage_bucket'] = bucket

            # Build success message
            if pdf_uploaded and chunks_uploaded == len(context.chunks):
                message = f"✅ Stored PDF and {chunks_uploaded} chunks in MinIO"
            elif pdf_uploaded:
                message = f"⚠️  Stored PDF and {chunks_uploaded}/{len(context.chunks)} chunks in MinIO"
            elif chunks_uploaded > 0:
                message = f"⚠️  PDF upload skipped (deadlock), stored {chunks_uploaded} chunks in MinIO"
            else:
                message = f"⚠️  MinIO storage failed, but data is in Milvus (critical)"

            # Always return success - MinIO is optional, Milvus is critical
            return StageResult(
                success=True,  # Always success!
                stage_name=self.name,
                message=message,
                metadata={
                    "pdf_uploaded": pdf_uploaded,
                    "chunks_uploaded": chunks_uploaded,
                    "total_chunks": len(context.chunks),
                    "bucket": bucket,
                    "pdf_path": storage_paths.get('pdf', None),
                    "chunks_path": storage_paths.get('chunks', None),
                    "partial_upload": not pdf_uploaded or chunks_uploaded < len(context.chunks)
                }
            )

        except Exception as e:
            # Outer exception handler - catastrophic MinIO failure
            # But still return success because Milvus (critical) already succeeded
            self.logger.error(f"⚠️  MinIO storage failed completely: {e}")
            self.logger.warning(f"⚠️  Document is in Milvus but not in MinIO storage")

            # Check for common storage errors (for logging)
            error_msg = str(e).lower()
            if "connection" in error_msg or "endpoint" in error_msg:
                error_detail = "Failed to connect to MinIO"
            elif "bucket" in error_msg and ("not exist" in error_msg or "not found" in error_msg):
                error_detail = f"MinIO bucket '{context.get_bucket_name()}' does not exist"
            elif "permission" in error_msg or "access denied" in error_msg:
                error_detail = "MinIO permission denied"
            elif "deadlock" in error_msg:
                error_detail = "MinIO deadlock detected"
            else:
                error_detail = f"MinIO storage error: {type(e).__name__}"

            self.logger.warning(f"⚠️  Error detail: {error_detail}")

            # Update stats to show failure
            context.stats['pdf_uploaded'] = False
            context.stats['chunks_uploaded'] = 0
            context.stats['storage_error'] = error_detail

            # Return success with warning - MinIO is optional
            return StageResult(
                success=True,  # Still success!
                stage_name=self.name,
                message=f"⚠️  MinIO storage failed: {error_detail}, but document is in Milvus",
                metadata={
                    "pdf_uploaded": False,
                    "chunks_uploaded": 0,
                    "total_chunks": len(context.chunks),
                    "storage_failed": True,
                    "error_type": type(e).__name__,
                    "error_detail": error_detail
                }
            )

    async def rollback(self, context: PipelineContext) -> None:
        """
        Rollback storage by deleting uploaded files

        This is called if later stages fail (though storage is the second-to-last stage).
        Rollback is best-effort and non-blocking.
        """
        if not context.storage_paths:
            self.logger.info(f"[{self.name}] No storage to rollback")
            return

        # Check if anything was actually uploaded
        pdf_uploaded = context.stats.get('pdf_uploaded', False)
        chunks_uploaded = context.stats.get('chunks_uploaded', 0)

        if not pdf_uploaded and chunks_uploaded == 0:
            self.logger.info(f"[{self.name}] Nothing was uploaded to MinIO, no rollback needed")
            return

        try:
            self.logger.warning(f"🔄 Rolling back MinIO storage: deleting document {context.document_id}")

            # Delete document and all related files (PDF, chunks, metadata)
            deleted = storage.delete_document(context.document_id)

            if deleted:
                self.logger.info(f"✅ Rolled back MinIO storage for document {context.document_id}")
            else:
                self.logger.warning(f"⚠️  Failed to fully rollback MinIO storage for document {context.document_id}")

        except Exception as e:
            # Rollback failure is not critical - just log warning
            self.logger.warning(f"⚠️  MinIO rollback failed: {e}")
            self.logger.warning(f"⚠️  Manual cleanup may be needed for document {context.document_id}")
            # Don't raise - rollback is best effort, don't block pipeline

    def _prepare_document_metadata(self, context: PipelineContext) -> Dict:
        """
        Prepare comprehensive document metadata for storage

        Args:
            context: Pipeline context with all document information

        Returns:
            Dictionary with document metadata
        """
        metadata = {
            "document_id": context.document_id,
            "file_hash": context.validation_result.file_hash if context.validation_result else "",
            "original_filename": context.filename,
            "document_size_bytes": len(context.file_data),
            "chunks_count": len(context.chunks)
        }

        # Add validation metadata if available
        if context.validation_result:
            metadata["document_type"] = context.validation_result.document_type
            # Extract status safely (might be string or enum)
            status_value = context.validation_result.status.value if hasattr(context.validation_result.status, 'value') else context.validation_result.status
            metadata["validation_status"] = status_value
            metadata["validation_timestamp"] = context.validation_result.validation_timestamp.isoformat()

            # Add extracted metadata
            if context.validation_result.metadata:
                metadata["extracted_metadata"] = {
                    "title": context.validation_result.metadata.title,
                    "author": context.validation_result.metadata.author,
                    "page_count": context.validation_result.metadata.page_count,
                    "language": context.validation_result.metadata.language
                }

            # Add content info
            if context.validation_result.content_info:
                metadata["content_analysis"] = context.validation_result.content_info

        # Add pipeline statistics
        if context.stats:
            metadata["processing_stats"] = {
                "pages_extracted": context.stats.get('pages_extracted'),
                "chunks_created": context.stats.get('chunks_created'),
                "avg_chunk_tokens": context.stats.get('avg_chunk_tokens'),
                "chunking_method": context.stats.get('chunking_method'),
                "embedding_model": context.stats.get('embedding_model'),
                "embeddings_generated": context.stats.get('embeddings_generated')
            }

        return metadata

    def _log_storage_stats(self, context: PipelineContext, storage_paths: Dict, chunks_uploaded: int, pdf_uploaded: bool) -> None:
        """
        Log detailed storage statistics

        Args:
            context: Pipeline context
            storage_paths: Storage paths dictionary
            chunks_uploaded: Number of chunks successfully uploaded
            pdf_uploaded: Whether PDF was uploaded successfully
        """
        self.logger.info(f"📊 Storage Statistics:")
        self.logger.info(f"   Bucket: {context.get_bucket_name()}")
        self.logger.info(f"   PDF Size: {len(context.file_data) / 1024:.2f} KB")

        if pdf_uploaded:
            self.logger.info(f"   PDF Status: ✅ Uploaded")
            self.logger.info(f"   PDF Path: {storage_paths.get('pdf', 'N/A')}")
        else:
            self.logger.warning(f"   PDF Status: ⚠️  Not uploaded (deadlock or error)")

        self.logger.info(f"   Chunks Uploaded: {chunks_uploaded}/{len(context.chunks)}")
        self.logger.info(f"   Chunks Path: {storage_paths.get('chunks', 'N/A')}")

        # Calculate total storage size
        total_size_mb = len(context.file_data) / (1024 * 1024)
        estimated_chunks_size_mb = sum(len(chunk.text.encode('utf-8')) for chunk in context.chunks) / (1024 * 1024)
        total_size_mb += estimated_chunks_size_mb

        self.logger.info(f"   Total Storage: {total_size_mb:.2f} MB")
