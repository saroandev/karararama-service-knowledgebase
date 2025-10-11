"""
Parsing stage for document processing pipeline

This stage extracts text from PDF documents using PDFParser.
"""
from typing import List

from app.core.orchestrator.stages.base import PipelineStage, StageResult
from app.core.orchestrator.pipeline_context import PipelineContext
from app.core.parsing import default_parser
from schemas.parsing.page import PageContent


class ParsingStage(PipelineStage):
    """
    Stage 2: Document Parsing

    Parses the document and extracts text from each page:
    - Uses PyMuPDF for PDF text extraction
    - Preserves page numbers and metadata
    - Cleans and normalizes text
    - Detects tables, images, and links

    Input (from context):
        - validation_result: ValidationResult (contains pdf_data)

    Output (to context):
        - pages: List[PageContent]
    """

    @property
    def name(self) -> str:
        return "parsing"

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute parsing stage

        Args:
            context: Pipeline context with validation_result

        Returns:
            StageResult indicating parsing success/failure
        """
        self.logger.info(f"📄 Parsing document: {context.filename}")

        # Validate input
        error = self.validate_input(context, 'validation_result')
        if error:
            return StageResult(
                success=False,
                stage_name=self.name,
                error=error
            )

        # Check if validation result has PDF data
        if not context.validation_result.pdf_data:
            return StageResult(
                success=False,
                stage_name=self.name,
                error="PDF data not found in validation result"
            )

        try:
            # Extract text using PDFParser
            pages, document_metadata = default_parser.extract_text(
                file_data=context.validation_result.pdf_data,
                file_type='pdf'
            )

            # Validate extraction result
            if not pages or len(pages) == 0:
                return StageResult(
                    success=False,
                    stage_name=self.name,
                    error="No pages extracted from document (document may be empty or scanned)",
                    metadata={
                        "pages_extracted": 0,
                        "suggestion": "Document may require OCR or may be empty"
                    }
                )

            # Store pages in context
            context.pages = pages

            # Log parsing statistics
            self._log_parsing_stats(pages)

            # Update context stats
            context.stats['pages_extracted'] = len(pages)
            context.stats['total_characters'] = sum(len(page.text) for page in pages)
            context.stats['total_words'] = sum(
                page.metadata.get('word_count', len(page.text.split()))
                for page in pages
            )

            # Success
            return StageResult(
                success=True,
                stage_name=self.name,
                message=f"✅ Extracted {len(pages)} pages with {context.stats['total_words']} words",
                metadata={
                    "pages_extracted": len(pages),
                    "total_characters": context.stats['total_characters'],
                    "total_words": context.stats['total_words'],
                    "has_tables": any(page.metadata.get('has_tables', False) for page in pages),
                    "has_images": any(page.metadata.get('has_images', False) for page in pages),
                }
            )

        except Exception as e:
            self.logger.exception(f"Parsing error: {e}")
            return StageResult(
                success=False,
                stage_name=self.name,
                error=f"Failed to parse document: {str(e)}",
                metadata={
                    "exception_type": type(e).__name__
                }
            )

    async def rollback(self, context: PipelineContext) -> None:
        """
        No rollback needed for parsing stage (read-only operation)
        """
        self.logger.info(f"[{self.name}] No rollback needed (read-only stage)")

    def _log_parsing_stats(self, pages: List[PageContent]) -> None:
        """
        Log detailed parsing statistics

        Args:
            pages: List of extracted PageContent objects
        """
        self.logger.info(f"📊 Parsing Statistics:")
        self.logger.info(f"   Pages Extracted: {len(pages)}")

        # Calculate statistics
        total_chars = sum(len(page.text) for page in pages)
        total_words = sum(page.metadata.get('word_count', len(page.text.split())) for page in pages)
        avg_words_per_page = total_words / len(pages) if pages else 0

        self.logger.info(f"   Total Characters: {total_chars:,}")
        self.logger.info(f"   Total Words: {total_words:,}")
        self.logger.info(f"   Avg Words/Page: {avg_words_per_page:.1f}")

        # Count special features
        pages_with_tables = sum(1 for page in pages if page.metadata.get('has_tables', False))
        pages_with_images = sum(1 for page in pages if page.metadata.get('has_images', False))
        pages_with_links = sum(1 for page in pages if page.metadata.get('has_links', False))

        if pages_with_tables > 0:
            self.logger.info(f"   📊 Pages with Tables: {pages_with_tables}")
        if pages_with_images > 0:
            self.logger.info(f"   🖼️  Pages with Images: {pages_with_images}")
        if pages_with_links > 0:
            self.logger.info(f"   🔗 Pages with Links: {pages_with_links}")
