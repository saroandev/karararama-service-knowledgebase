"""
Main document validator class
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import UploadFile
from pymilvus import Collection

from app.core.validation.base import BaseValidator
from app.core.validation.type_detector import DocumentTypeDetector
from app.core.validation.metadata_extractor import MetadataExtractor
from app.core.validation.content_analyzer import ContentAnalyzer
from app.core.validation.utils import (
    generate_document_hash,
    calculate_file_metrics,
    estimate_processing_requirements
)
from schemas.validation import (
    ValidationStatus,
    ValidationResult,
    DocumentType,
    ContentInfo
)

logger = logging.getLogger(__name__)


class DocumentValidator(BaseValidator):
    """Main document validator orchestrator"""

    def __init__(self):
        """Initialize document validator with component validators"""
        super().__init__()
        self.type_detector = DocumentTypeDetector()
        self.metadata_extractor = MetadataExtractor()
        self.content_analyzer = ContentAnalyzer()

    def _define_validation_rules(self) -> Dict[str, Any]:
        """Define validation rules for documents"""
        return {
            "max_file_size": 104857600,  # 100MB
            "max_page_count": 1000,
            "min_content_length": 100,  # Minimum 100 characters
            "supported_extensions": ['pdf', 'txt', 'docx', 'html', 'md'],
            "required_metadata_quality": 0.3,  # Minimum metadata quality score
            "max_empty_page_ratio": 0.5  # Maximum 50% empty pages
        }

    async def validate(
        self,
        file: UploadFile,
        milvus_manager: Any = None,
        scope: Any = None
    ) -> ValidationResult:
        """
        Validate document and prepare for processing

        Args:
            file: Uploaded file object
            milvus_manager: Milvus manager for duplicate checking
            scope: ScopeIdentifier for multi-tenant collection (optional)

        Returns:
            ValidationResult with validation status and metadata
        """
        start_time = datetime.now()
        self.log_validation_start(file.filename)

        try:
            # Read file data
            file_data = await file.read()
            await file.seek(0)  # Reset file pointer for potential reuse

            # Calculate file metrics
            file_metrics = calculate_file_metrics(file_data)

            # Generate document hash and ID
            document_id, md5_hash, _ = generate_document_hash(file_data)

            # Initialize validation result
            validation_result = ValidationResult(
                status=ValidationStatus.VALID,
                document_id=document_id,
                file_hash=md5_hash,
                document_type=DocumentType.UNKNOWN.value,
                file_name=file.filename,
                file_size=file_metrics['file_size_bytes']
            )

            # Step 1: Check for duplicate (if Milvus manager provided)
            if milvus_manager:
                duplicate_check = await self._check_duplicate(document_id, milvus_manager, scope)
                if duplicate_check['exists']:
                    validation_result.status = ValidationStatus.EXISTS
                    validation_result.existing_metadata = duplicate_check['metadata']
                    validation_result.existing_chunks_count = duplicate_check['chunks_count']
                    validation_result.processing_time = (datetime.now() - start_time).total_seconds()

                    self.log_validation_end(file.filename, ValidationStatus.EXISTS)
                    validation_result.add_info(f"Document already exists with {duplicate_check['chunks_count']} chunks")
                    return validation_result

                validation_result.add_check("duplicate_check", True, "Document is not a duplicate")

            # Step 2: Basic file validation
            # Check file size
            size_valid, size_error = self.check_file_size(
                file_metrics['file_size_bytes'],
                self._validation_rules['max_file_size']
            )
            validation_result.add_check("file_size", size_valid, size_error or "File size is within limits")
            if not size_valid:
                validation_result.status = ValidationStatus.INVALID
                validation_result.add_error(size_error)
                validation_result.processing_time = (datetime.now() - start_time).total_seconds()
                return validation_result

            # Check file extension
            ext_valid, ext_error = self.check_file_extension(
                file.filename,
                self._validation_rules['supported_extensions']
            )
            validation_result.add_check("file_extension", ext_valid, ext_error or "File extension is supported")
            if not ext_valid:
                validation_result.add_warning(ext_error)

            # Step 3: Detect document type
            document_type, _ = self.type_detector.detect(
                file_data,
                file.filename,
                file.content_type
            )
            validation_result.document_type = document_type.value
            validation_result.add_check(
                "document_type_detection",
                document_type != DocumentType.UNKNOWN,
                f"Document type detected: {document_type.value}"
            )

            if document_type == DocumentType.UNKNOWN:
                validation_result.status = ValidationStatus.INVALID
                validation_result.add_error("Could not determine document type")
                validation_result.processing_time = (datetime.now() - start_time).total_seconds()
                return validation_result

            # Step 4: Extract metadata
            metadata = self.metadata_extractor.extract(file_data, file.filename, document_type)
            validation_result.metadata = metadata

            # Check metadata quality
            metadata_quality = self.metadata_extractor.get_metadata_quality_score(metadata)
            validation_result.add_check(
                "metadata_quality",
                metadata_quality >= self._validation_rules['required_metadata_quality'],
                f"Metadata quality score: {metadata_quality:.2f}"
            )

            if metadata_quality < self._validation_rules['required_metadata_quality']:
                validation_result.add_warning("Low metadata quality - some information may be missing")

            # Step 5: Analyze content
            content_info = self.content_analyzer.analyze(
                file_data,
                document_type,
                metadata.page_count
            )
            validation_result.content_info = content_info.model_dump()

            # Content validation checks
            if content_info.word_count < 10:
                validation_result.status = ValidationStatus.INVALID
                validation_result.add_error("Document appears to be empty or contains too little text")
                validation_result.add_check("content_check", False, "Insufficient content")
            else:
                validation_result.add_check("content_check", True, f"Content validated: {content_info.word_count} words")

            # Check empty page ratio
            if content_info.page_count > 0:
                empty_ratio = content_info.empty_page_count / content_info.page_count
                if empty_ratio > self._validation_rules['max_empty_page_ratio']:
                    validation_result.add_warning(f"High empty page ratio: {empty_ratio:.1%}")
                    validation_result.status = ValidationStatus.WARNING

            # Check for encryption
            if content_info.has_encryption:
                validation_result.status = ValidationStatus.INVALID
                validation_result.add_error("Document is encrypted and cannot be processed")
                validation_result.add_check("encryption_check", False, "Document is encrypted")
            else:
                validation_result.add_check("encryption_check", True, "Document is not encrypted")

            # Step 6: Generate processing hints
            processing_hints = self._generate_processing_hints(
                document_type,
                content_info,
                file_metrics
            )
            validation_result.processing_hints = processing_hints

            # Step 7: Final validation status
            if validation_result.status == ValidationStatus.VALID and len(validation_result.warnings) > 0:
                validation_result.status = ValidationStatus.WARNING

            # Store PDF data for further processing
            validation_result.pdf_data = file_data

            # Calculate processing time
            validation_result.processing_time = (datetime.now() - start_time).total_seconds()

            self.log_validation_end(file.filename, validation_result.status)

            # Add summary
            validation_result.add_info(
                f"Validation completed: {validation_result.get_summary()['checks_passed']}/{validation_result.get_summary()['checks_total']} checks passed"
            )

            return validation_result

        except Exception as e:
            self.log_validation_error(file.filename, e)

            # Create error result
            return ValidationResult(
                status=ValidationStatus.INVALID,
                document_id=document_id if 'document_id' in locals() else "",
                file_hash=md5_hash if 'md5_hash' in locals() else "",
                document_type=DocumentType.UNKNOWN.value,
                file_name=file.filename,
                file_size=0,
                errors=[str(e)],
                processing_time=(datetime.now() - start_time).total_seconds()
            )

    async def _check_duplicate(
        self,
        document_id: str,
        milvus_manager: Any,
        scope: Any = None
    ) -> Dict[str, Any]:
        """
        Check if document already exists in Milvus

        Args:
            document_id: Document identifier
            milvus_manager: Milvus manager instance
            scope: ScopeIdentifier for multi-tenant collection (optional)

        Returns:
            Dictionary with existence check result
        """
        try:
            # Use scope-aware collection if provided (auto-create for ingest validation operation)
            collection: Collection = milvus_manager.get_collection(scope, auto_create=True)

            # Query for existing document
            search_results = collection.query(
                expr=f'document_id == "{document_id}"',
                output_fields=['id', 'metadata'],
                limit=10  # Get a sample of chunks
            )

            if search_results:
                # Document exists
                logger.info(f"Document {document_id} already exists with {len(search_results)} chunks found")

                # Extract metadata from first chunk
                metadata = {}
                if search_results and 'metadata' in search_results[0]:
                    try:
                        first_metadata = search_results[0]['metadata']
                        if isinstance(first_metadata, str):
                            metadata = json.loads(first_metadata)
                        elif isinstance(first_metadata, dict):
                            metadata = first_metadata
                    except:
                        pass

                return {
                    'exists': True,
                    'metadata': metadata,
                    'chunks_count': len(search_results)
                }

            return {
                'exists': False,
                'metadata': None,
                'chunks_count': 0
            }

        except Exception as e:
            logger.warning(f"Could not check document existence: {e}")
            # If we can't check, assume it doesn't exist
            return {
                'exists': False,
                'metadata': None,
                'chunks_count': 0
            }

    def _generate_processing_hints(
        self,
        document_type: DocumentType,
        content_info: ContentInfo,
        file_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate processing hints based on validation results

        Args:
            document_type: Type of document
            content_info: Content analysis results
            file_metrics: File metrics

        Returns:
            Dictionary with processing hints
        """
        # Get base recommendations
        hints = estimate_processing_requirements(
            file_metrics['file_size_bytes'],
            content_info.page_count,
            content_info.has_images,
            content_info.has_tables
        )

        # Get type-specific hints
        type_hints = self.type_detector.get_processing_hints(document_type)
        hints.update(type_hints)

        # Get content-based recommendations
        content_recommendations = self.content_analyzer.get_processing_recommendations(content_info)
        hints.update(content_recommendations)

        # Add language hint
        if content_info.detected_languages:
            hints['primary_language'] = content_info.detected_languages[0]
            hints['multi_language'] = len(content_info.detected_languages) > 1

        # Add quality indicators
        hints['has_metadata'] = True  # We always extract some metadata
        hints['requires_ocr'] = content_info.requires_ocr
        hints['complex_layout'] = content_info.has_tables or (content_info.image_count > 5)

        return hints