"""
Validation result schemas
"""
from enum import Enum
from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """Status of document validation"""
    VALID = "valid"       # Document is valid and can be processed
    INVALID = "invalid"   # Document is invalid and cannot be processed
    EXISTS = "exists"     # Document already exists in database
    WARNING = "warning"   # Document has warnings but can be processed


class DocumentMetadata(BaseModel):
    """Extended document metadata from validation"""
    # Basic metadata
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None

    # File metadata
    page_count: int = 0
    file_size: int = 0  # bytes
    file_name: str = ""

    # Timestamps
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    uploaded_at: datetime = Field(default_factory=datetime.now)

    # Content metadata
    language: Optional[str] = None
    encoding: str = "utf-8"

    # Hash values
    md5_hash: Optional[str] = None
    sha256_hash: Optional[str] = None


class ValidationCheck(BaseModel):
    """Individual validation check result"""
    check_name: str
    passed: bool
    message: Optional[str] = None
    severity: str = "info"  # info, warning, error


class ValidationResult(BaseModel):
    """Complete validation result"""
    # Status
    status: ValidationStatus
    document_id: str
    file_hash: str

    # Document information
    document_type: str  # From DocumentType enum
    file_name: str
    file_size: int

    # For existing documents
    existing_metadata: Optional[Dict[str, Any]] = None
    existing_chunks_count: Optional[int] = None

    # For new documents
    metadata: Optional[DocumentMetadata] = None
    content_info: Optional[Dict[str, Any]] = None

    # Validation checks performed
    validation_checks: List[ValidationCheck] = Field(default_factory=list)

    # Processing information
    pdf_data: Optional[bytes] = Field(default=None, exclude=True)  # Exclude from serialization
    processing_time: float = 0.0
    validation_timestamp: datetime = Field(default_factory=datetime.now)

    # Messages and warnings
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    info_messages: List[str] = Field(default_factory=list)

    # Processing hints for downstream components
    processing_hints: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            bytes: lambda v: None  # Don't serialize bytes
        }

    def add_check(self, name: str, passed: bool, message: str = None, severity: str = "info"):
        """Add a validation check result"""
        self.validation_checks.append(ValidationCheck(
            check_name=name,
            passed=passed,
            message=message,
            severity=severity
        ))

    def add_warning(self, message: str):
        """Add a warning message"""
        self.warnings.append(message)

    def add_error(self, message: str):
        """Add an error message"""
        self.errors.append(message)

    def add_info(self, message: str):
        """Add an info message"""
        self.info_messages.append(message)

    def is_valid(self) -> bool:
        """Check if validation passed"""
        return self.status in [ValidationStatus.VALID, ValidationStatus.WARNING]

    def is_duplicate(self) -> bool:
        """Check if document already exists"""
        return self.status == ValidationStatus.EXISTS

    def has_warnings(self) -> bool:
        """Check if there are any warnings"""
        return len(self.warnings) > 0 or self.status == ValidationStatus.WARNING

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of validation result"""
        return {
            "status": self.status,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "checks_passed": sum(1 for check in self.validation_checks if check.passed),
            "checks_total": len(self.validation_checks),
            "has_warnings": self.has_warnings(),
            "warning_count": len(self.warnings),
            "error_count": len(self.errors)
        }