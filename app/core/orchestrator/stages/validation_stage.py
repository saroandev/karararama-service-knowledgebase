"""
Validation stage for document processing pipeline

This stage validates the document before processing using DocumentValidator.
"""
import io
from typing import Optional

from fastapi import UploadFile

from app.core.orchestrator.stages.base import PipelineStage, StageResult
from app.core.orchestrator.pipeline_context import PipelineContext
from app.core.validation import get_document_validator
from schemas.validation.validation_result import ValidationStatus
from api.core.milvus_manager import milvus_manager


class ValidationStage(PipelineStage):
    """
    Stage 1: Document Validation

    Validates the document using DocumentValidator:
    - File size check
    - File type detection
    - Content analysis
    - Metadata extraction
    - Duplicate detection (if collection exists)
    - Encryption check
    - Quality assessment

    Input (from context):
        - file_data: bytes
        - filename: str
        - scope_identifier: ScopeIdentifier (for duplicate check)

    Output (to context):
        - validation_result: ValidationResult
    """

    @property
    def name(self) -> str:
        return "validation"

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute validation stage

        Args:
            context: Pipeline context with file_data and filename

        Returns:
            StageResult indicating validation success/failure
        """
        self.logger.info(f"🔍 Validating document: {context.filename}")

        # Validate input
        error = self.validate_input(context, 'file_data', 'filename', 'scope_identifier')
        if error:
            return StageResult(
                success=False,
                stage_name=self.name,
                error=error
            )

        try:
            # Create UploadFile-like object from bytes
            # DocumentValidator expects UploadFile, so we create a compatible object
            upload_file = self._create_upload_file(
                file_data=context.file_data,
                filename=context.filename
            )

            # Get document validator (use context manager properly)
            async with get_document_validator() as validator:
                # Pass milvus_manager and scope for duplicate detection
                validation_result = await validator.validate(
                    file=upload_file,
                    milvus_manager=milvus_manager,  # Enable duplicate check
                    scope=context.scope_identifier  # Pass scope for collection lookup
                )

            # Store validation result in context
            context.validation_result = validation_result

            # Log validation details
            self._log_validation_details(validation_result)

            # Check validation status
            if validation_result.status == ValidationStatus.INVALID:
                # Document is invalid, stop pipeline
                error_msg = "; ".join(validation_result.errors) if validation_result.errors else "Unknown validation error"

                # Extract status safely
                status_value = validation_result.status.value if hasattr(validation_result.status, 'value') else validation_result.status

                return StageResult(
                    success=False,
                    stage_name=self.name,
                    error=f"Document validation failed: {error_msg}",
                    metadata={
                        "validation_status": status_value,
                        "error_count": len(validation_result.errors),
                        "warning_count": len(validation_result.warnings)
                    }
                )

            if validation_result.status == ValidationStatus.EXISTS:
                # Document already exists, stop pipeline
                # The endpoint will handle creating ExistingDocumentResponse
                self.logger.warning(f"⚠️  Document already exists: {context.document_id}")

                # Extract status safely
                status_value = validation_result.status.value if hasattr(validation_result.status, 'value') else validation_result.status

                return StageResult(
                    success=False,
                    stage_name=self.name,
                    message="Document already exists in database",
                    metadata={
                        "validation_status": status_value,
                        "existing_chunks_count": validation_result.existing_chunks_count,
                        "existing_metadata": validation_result.existing_metadata
                    }
                )

            # Success (VALID or WARNING)
            status_emoji = "⚠️" if validation_result.status == ValidationStatus.WARNING else "✅"

            # Extract status safely
            status_value = validation_result.status.value if hasattr(validation_result.status, 'value') else validation_result.status

            return StageResult(
                success=True,
                stage_name=self.name,
                message=f"{status_emoji} Document validated: {validation_result.document_type} ({validation_result.file_size} bytes)",
                metadata={
                    "validation_status": status_value,
                    "document_type": validation_result.document_type,
                    "page_count": validation_result.metadata.page_count if validation_result.metadata else 0,
                    "warning_count": len(validation_result.warnings),
                    "processing_time": validation_result.processing_time
                }
            )

        except Exception as e:
            self.logger.exception(f"Validation error: {e}")
            return StageResult(
                success=False,
                stage_name=self.name,
                error=f"Validation exception: {str(e)}"
            )

    async def rollback(self, context: PipelineContext) -> None:
        """
        No rollback needed for validation stage (read-only operation)
        """
        self.logger.info(f"[{self.name}] No rollback needed (read-only stage)")

    def _create_upload_file(self, file_data: bytes, filename: str) -> UploadFile:
        """
        Create UploadFile-like object from bytes

        Args:
            file_data: File content as bytes
            filename: Filename

        Returns:
            UploadFile object
        """
        # Detect content type from filename
        content_type = "application/pdf"  # Default to PDF
        if filename.lower().endswith('.txt'):
            content_type = "text/plain"
        elif filename.lower().endswith('.docx'):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif filename.lower().endswith('.html'):
            content_type = "text/html"

        # Create UploadFile with BytesIO
        return UploadFile(
            filename=filename,
            file=io.BytesIO(file_data),
            size=len(file_data),
            headers={"content-type": content_type}
        )

    def _log_validation_details(self, validation_result) -> None:
        """
        Log detailed validation results

        Args:
            validation_result: ValidationResult object
        """
        summary = validation_result.get_summary()

        self.logger.info(f"📊 Validation Summary:")
        # status is already a string (or has .value if it's enum)
        status_str = validation_result.status.value if hasattr(validation_result.status, 'value') else validation_result.status
        self.logger.info(f"   Status: {status_str}")
        self.logger.info(f"   Document Type: {validation_result.document_type}")
        self.logger.info(f"   Checks: {summary['checks_passed']}/{summary['checks_total']} passed")

        if validation_result.metadata:
            self.logger.info(f"   Pages: {validation_result.metadata.page_count}")
            self.logger.info(f"   Size: {validation_result.file_size} bytes")

        if validation_result.warnings:
            self.logger.warning(f"   ⚠️  Warnings: {len(validation_result.warnings)}")
            for warning in validation_result.warnings:
                self.logger.warning(f"      - {warning}")

        if validation_result.errors:
            self.logger.error(f"   ❌ Errors: {len(validation_result.errors)}")
            for error in validation_result.errors:
                self.logger.error(f"      - {error}")
