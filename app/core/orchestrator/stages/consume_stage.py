"""
Consume stage for document processing pipeline

This stage reports usage to OneDocs Auth Service for credit tracking.
"""
from typing import Dict, Any

from app.core.orchestrator.stages.base import PipelineStage, StageResult
from app.core.orchestrator.pipeline_context import PipelineContext
from app.services.auth_service import get_auth_service_client
from app.config.constants import ServiceType


class ConsumeStage(PipelineStage):
    """
    Stage 7: Usage Consumption (Auth Service)

    Reports usage to OneDocs Auth Service:
    - Calculates tokens used from embeddings
    - Sends usage data with metadata
    - Updates remaining credits
    - Non-blocking: failure doesn't stop pipeline

    Input (from context):
        - user: UserContext
        - embeddings: List[np.ndarray]
        - pages: List[PageContent]
        - chunks: List[SimpleChunk]
        - validation_result: ValidationResult
        - file_data: bytes

    Output (to context):
        - usage_result: Dict with remaining_credits and response data
    """

    @property
    def name(self) -> str:
        return "consume"

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute usage consumption stage

        Args:
            context: Pipeline context with usage data

        Returns:
            StageResult indicating consumption success/failure

        Note:
            This stage always returns success=True even if auth service fails.
            Usage tracking failure should NOT block document ingestion.
        """
        self.logger.info(f"💳 Reporting usage to auth service")

        # Validate input
        error = self.validate_input(context, 'user', 'embeddings')
        if error:
            # Don't fail pipeline - just log warning
            self.logger.warning(f"⚠️  Cannot report usage: {error}")
            return StageResult(
                success=True,  # Still success!
                stage_name=self.name,
                message="⚠️  Usage reporting skipped due to missing data",
                metadata={"skipped": True, "reason": error}
            )

        try:
            # Calculate usage metrics
            # tokens_used = document count (always 1 per ingestion)
            documents_uploaded = 1

            # Calculate document size in MB
            size_mb = round(len(context.file_data) / (1024 * 1024), 2) if context.file_data else 0

            # Prepare metadata with size information
            usage_metadata = self._prepare_usage_metadata(context)
            usage_metadata["size_mb"] = size_mb
            usage_metadata["documents_uploaded"] = documents_uploaded

            # Get auth service client
            auth_client = get_auth_service_client()

            # Report usage to auth service
            self.logger.info(f"📡 Calling auth service: user={context.user.user_id}, documents={documents_uploaded}, size={size_mb}MB")

            usage_result = await auth_client.consume_usage(
                user_id=context.user.user_id,
                service_type=ServiceType.INGEST,
                tokens_used=documents_uploaded,  # 1 document = 1 token
                processing_time=context.get_total_duration(),
                metadata=usage_metadata
            )

            # Store result in context
            context.usage_result = usage_result

            # Log consumption details
            self._log_consumption_details(usage_result, documents_uploaded, size_mb)

            # Update context stats
            context.stats['usage_reported'] = True
            context.stats['documents_uploaded'] = documents_uploaded
            context.stats['size_mb'] = size_mb
            if usage_result.get("remaining_credits") is not None:
                context.stats['remaining_credits'] = usage_result.get("remaining_credits")

            # Success
            return StageResult(
                success=True,
                stage_name=self.name,
                message=f"✅ Usage reported: {documents_uploaded} document(s), {size_mb} MB",
                metadata={
                    "documents_uploaded": documents_uploaded,
                    "size_mb": size_mb,
                    "remaining_credits": usage_result.get("remaining_credits"),
                    "auth_service_response": usage_result.get("success", True)
                }
            )

        except Exception as e:
            # Auth service error - log but don't fail pipeline
            self.logger.warning(f"⚠️  Failed to report usage to auth service: {str(e)}")
            self.logger.warning(f"⚠️  Document ingestion will continue despite usage tracking failure")

            # Store partial result (use user's current credits as fallback)
            context.usage_result = {
                "success": False,
                "remaining_credits": context.user.remaining_credits,
                "error": str(e)
            }

            # Update context stats
            context.stats['usage_reported'] = False
            context.stats['usage_error'] = str(e)

            # Return success to continue pipeline
            return StageResult(
                success=True,  # Pipeline continues!
                stage_name=self.name,
                message=f"⚠️  Usage reporting failed but pipeline continues",
                metadata={
                    "usage_reported": False,
                    "error": str(e),
                    "fallback_credits": context.user.remaining_credits
                }
            )

    async def rollback(self, context: PipelineContext) -> None:
        """
        No rollback needed for consume stage

        Auth service doesn't support usage reversal.
        If pipeline fails after this stage, credits are already consumed.

        Note: In production, consider implementing a refund mechanism
        if later stages fail (e.g., storage failure after credit consumption).
        """
        self.logger.info(f"[{self.name}] No rollback needed (auth service doesn't support usage reversal)")

    def _prepare_usage_metadata(self, context: PipelineContext) -> Dict[str, Any]:
        """
        Prepare metadata for usage tracking

        Args:
            context: Pipeline context with all processing data

        Returns:
            Dictionary with usage metadata
        """
        metadata = {
            "filename": context.filename,
            "document_id": context.document_id,
            "chunks_created": len(context.chunks) if context.chunks else 0,
            "pages_count": len(context.pages) if context.pages else 0,
            "file_size_bytes": len(context.file_data) if context.file_data else 0
        }

        # Add document type from validation
        if context.validation_result:
            metadata["document_type"] = context.validation_result.document_type

        # Add collection info
        metadata["collection_name"] = context.get_collection_name()
        metadata["scope_type"] = context.scope_identifier.scope_type.value

        # Add embedding info
        if context.embeddings and len(context.embeddings) > 0:
            metadata["embedding_dimension"] = len(context.embeddings[0])

        # Add chunking stats
        if context.stats:
            if 'chunking_method' in context.stats:
                metadata["chunking_method"] = context.stats['chunking_method']
            if 'avg_chunk_tokens' in context.stats:
                metadata["avg_chunk_tokens"] = context.stats['avg_chunk_tokens']

        return metadata

    def _log_consumption_details(self, usage_result: Dict[str, Any], documents_uploaded: int, size_mb: float) -> None:
        """
        Log detailed usage consumption information

        Args:
            usage_result: Response from auth service
            documents_uploaded: Number of documents uploaded (always 1)
            size_mb: Document size in megabytes
        """
        self.logger.info(f"📊 Usage Consumption Details:")
        self.logger.info(f"   Documents Uploaded: {documents_uploaded}")
        self.logger.info(f"   Document Size: {size_mb} MB")

        if usage_result.get("remaining_credits") is not None:
            self.logger.info(f"   Remaining Credits: {usage_result.get('remaining_credits'):,}")

        if usage_result.get("success") is False:
            self.logger.warning(f"   ⚠️  Auth service reported error: {usage_result.get('error', 'Unknown')}")

        # Log additional response data
        if "usage_id" in usage_result:
            self.logger.info(f"   Usage ID: {usage_result['usage_id']}")
