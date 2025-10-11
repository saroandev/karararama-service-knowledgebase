"""
Chunking stage for document processing pipeline

This stage splits pages into chunks using token-based chunking with overlap.
"""
from typing import List

from app.core.orchestrator.stages.base import PipelineStage, StageResult
from app.core.orchestrator.pipeline_context import PipelineContext
from app.core.chunking import get_default_chunker
from schemas.internal.chunk import SimpleChunk


class ChunkingStage(PipelineStage):
    """
    Stage 3: Text Chunking

    Splits text into overlapping chunks with proper token limits:
    - Uses TextChunker with token-based splitting
    - Configurable chunk size (default: 512 tokens from settings)
    - Configurable overlap (default: 50 tokens from settings)
    - Preserves page number metadata
    - Generates unique chunk IDs

    This replaces the old basic "1 page = 1 chunk" approach with proper
    token-aware chunking that respects context boundaries.

    Input (from context):
        - pages: List[PageContent]
        - document_id: str

    Output (to context):
        - chunks: List[SimpleChunk]
    """

    @property
    def name(self) -> str:
        return "chunking"

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute chunking stage

        Args:
            context: Pipeline context with pages

        Returns:
            StageResult indicating chunking success/failure
        """
        self.logger.info(f"✂️  Chunking document: {context.filename}")

        # Validate input
        error = self.validate_input(context, 'pages', 'document_id')
        if error:
            return StageResult(
                success=False,
                stage_name=self.name,
                error=error
            )

        # Check if pages exist
        if not context.pages or len(context.pages) == 0:
            return StageResult(
                success=False,
                stage_name=self.name,
                error="No pages to chunk"
            )

        try:
            # Get default chunker (token-based with settings from config)
            chunker = get_default_chunker()

            # Chunk pages with page boundary preservation
            # This will chunk each page separately while respecting token limits
            chunks_with_metadata = chunker.chunk_pages(
                pages=context.pages,
                document_id=context.document_id,
                preserve_pages=True  # Keep page boundaries for better retrieval
            )

            # Convert to SimpleChunk objects (internal format)
            simple_chunks = self._convert_to_simple_chunks(chunks_with_metadata)

            # Validate chunking result
            if not simple_chunks or len(simple_chunks) == 0:
                return StageResult(
                    success=False,
                    stage_name=self.name,
                    error="Chunking produced no chunks",
                    metadata={
                        "pages_processed": len(context.pages)
                    }
                )

            # Store chunks in context
            context.chunks = simple_chunks

            # Log chunking statistics
            self._log_chunking_stats(simple_chunks, chunks_with_metadata)

            # Update context stats
            context.stats['chunks_created'] = len(simple_chunks)
            context.stats['avg_chunk_tokens'] = sum(
                chunk.token_count for chunk in chunks_with_metadata
            ) / len(chunks_with_metadata)
            context.stats['avg_chunk_chars'] = sum(
                len(chunk.text) for chunk in simple_chunks
            ) / len(simple_chunks)
            context.stats['chunking_method'] = 'token-based'
            context.stats['chunk_size_config'] = chunker.chunk_size
            context.stats['chunk_overlap_config'] = chunker.chunk_overlap

            # Success
            return StageResult(
                success=True,
                stage_name=self.name,
                message=f"✅ Created {len(simple_chunks)} chunks from {len(context.pages)} pages (avg {context.stats['avg_chunk_tokens']:.0f} tokens/chunk)",
                metadata={
                    "chunks_created": len(simple_chunks),
                    "pages_processed": len(context.pages),
                    "avg_tokens_per_chunk": context.stats['avg_chunk_tokens'],
                    "avg_chars_per_chunk": context.stats['avg_chunk_chars'],
                    "chunk_size_target": chunker.chunk_size,
                    "chunk_overlap": chunker.chunk_overlap,
                    "method": "token-based"
                }
            )

        except Exception as e:
            self.logger.exception(f"Chunking error: {e}")
            return StageResult(
                success=False,
                stage_name=self.name,
                error=f"Failed to chunk document: {str(e)}",
                metadata={
                    "exception_type": type(e).__name__,
                    "pages_attempted": len(context.pages)
                }
            )

    async def rollback(self, context: PipelineContext) -> None:
        """
        No rollback needed for chunking stage (read-only operation)
        """
        self.logger.info(f"[{self.name}] No rollback needed (read-only stage)")

    def _convert_to_simple_chunks(self, chunks_with_metadata: List) -> List[SimpleChunk]:
        """
        Convert Chunk objects to SimpleChunk objects

        Args:
            chunks_with_metadata: List of Chunk objects from chunker

        Returns:
            List of SimpleChunk objects
        """
        simple_chunks = []

        for chunk in chunks_with_metadata:
            # Extract page number from metadata (default to 1 if not found)
            page_number = chunk.metadata.get('page_number', 1)

            # Create SimpleChunk
            simple_chunk = SimpleChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page_number=page_number,
                chunk_index=chunk.chunk_index,
                metadata=chunk.metadata
            )

            simple_chunks.append(simple_chunk)

        return simple_chunks

    def _log_chunking_stats(self, simple_chunks: List[SimpleChunk], detailed_chunks: List) -> None:
        """
        Log detailed chunking statistics

        Args:
            simple_chunks: List of SimpleChunk objects
            detailed_chunks: List of detailed Chunk objects with token counts
        """
        self.logger.info(f"📊 Chunking Statistics:")
        self.logger.info(f"   Total Chunks: {len(simple_chunks)}")

        # Token statistics
        token_counts = [chunk.token_count for chunk in detailed_chunks]
        if token_counts:
            avg_tokens = sum(token_counts) / len(token_counts)
            min_tokens = min(token_counts)
            max_tokens = max(token_counts)
            self.logger.info(f"   Token Count: avg={avg_tokens:.0f}, min={min_tokens}, max={max_tokens}")

        # Character statistics
        char_counts = [len(chunk.text) for chunk in simple_chunks]
        if char_counts:
            avg_chars = sum(char_counts) / len(char_counts)
            self.logger.info(f"   Avg Characters: {avg_chars:.0f}")

        # Page distribution
        page_chunks = {}
        for chunk in simple_chunks:
            page_num = chunk.page_number
            page_chunks[page_num] = page_chunks.get(page_num, 0) + 1

        if page_chunks:
            self.logger.info(f"   Page Distribution: {len(page_chunks)} pages")
            # Log pages with many chunks (might indicate complex content)
            heavy_pages = [(page, count) for page, count in page_chunks.items() if count > 5]
            if heavy_pages:
                self.logger.info(f"   📝 Pages with >5 chunks: {heavy_pages[:5]}")  # Show first 5
