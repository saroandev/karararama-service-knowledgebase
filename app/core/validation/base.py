"""
Base validator class for document validation
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging

from schemas.validation import ValidationResult, ValidationStatus

logger = logging.getLogger(__name__)


class BaseValidator(ABC):
    """Abstract base class for all validators"""

    def __init__(self):
        """Initialize the validator"""
        self.logger = logger
        self._validation_rules = self._define_validation_rules()

    @abstractmethod
    def _define_validation_rules(self) -> Dict[str, Any]:
        """
        Define validation rules for this validator

        Returns:
            Dictionary of validation rules
        """
        pass

    @abstractmethod
    async def validate(self, *args, **kwargs) -> ValidationResult:
        """
        Perform validation

        Returns:
            ValidationResult object
        """
        pass

    def check_file_size(self, file_size: int, max_size: int = 104857600) -> tuple[bool, Optional[str]]:
        """
        Check if file size is within limits

        Args:
            file_size: Size of file in bytes
            max_size: Maximum allowed size in bytes (default 100MB)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if file_size <= 0:
            return False, "File is empty"
        if file_size > max_size:
            size_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds maximum limit of {size_mb}MB"
        return True, None

    def check_file_extension(self, filename: str, allowed_extensions: List[str]) -> tuple[bool, Optional[str]]:
        """
        Check if file extension is allowed

        Args:
            filename: Name of the file
            allowed_extensions: List of allowed extensions

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not filename:
            return False, "Filename is empty"

        extension = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        if not extension:
            return False, "File has no extension"

        if extension not in allowed_extensions:
            return False, f"File type '.{extension}' is not supported. Allowed types: {', '.join(allowed_extensions)}"

        return True, None

    def validate_metadata(self, metadata: Dict[str, Any]) -> List[str]:
        """
        Validate metadata structure

        Args:
            metadata: Metadata dictionary to validate

        Returns:
            List of validation warnings
        """
        warnings = []

        # Check for required metadata fields
        if not metadata:
            warnings.append("No metadata provided")
            return warnings

        # Check for empty values
        for key, value in metadata.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                warnings.append(f"Metadata field '{key}' is empty")

        return warnings

    def create_validation_result(
        self,
        status: ValidationStatus,
        document_id: str,
        file_hash: str,
        **kwargs
    ) -> ValidationResult:
        """
        Create a validation result object

        Args:
            status: Validation status
            document_id: Document identifier
            file_hash: File hash
            **kwargs: Additional fields for ValidationResult

        Returns:
            ValidationResult object
        """
        return ValidationResult(
            status=status,
            document_id=document_id,
            file_hash=file_hash,
            **kwargs
        )

    def log_validation_start(self, identifier: str):
        """Log the start of validation"""
        self.logger.info(f"Starting validation for: {identifier}")

    def log_validation_end(self, identifier: str, status: ValidationStatus):
        """Log the end of validation"""
        self.logger.info(f"Validation completed for {identifier}: {status}")

    def log_validation_error(self, identifier: str, error: Exception):
        """Log validation error"""
        self.logger.error(f"Validation error for {identifier}: {str(error)}")

    def is_pdf(self, file_data: bytes) -> bool:
        """
        Check if file data is a PDF

        Args:
            file_data: File content as bytes

        Returns:
            True if PDF, False otherwise
        """
        if not file_data or len(file_data) < 4:
            return False
        return file_data[:4] == b'%PDF'

    def is_text_file(self, file_data: bytes) -> bool:
        """
        Check if file is a text file

        Args:
            file_data: File content as bytes

        Returns:
            True if likely text file, False otherwise
        """
        try:
            file_data[:1024].decode('utf-8')
            return True
        except (UnicodeDecodeError, AttributeError):
            return False