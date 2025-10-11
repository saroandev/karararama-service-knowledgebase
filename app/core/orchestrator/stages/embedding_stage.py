"""
Embedding stage for document processing pipeline

This stage generates vector embeddings for chunks using OpenAI or local models.
"""
import numpy as np
from typing import List

from app.core.orchestrator.stages.base import PipelineStage, StageResult
from app.core.orchestrator.pipeline_context import PipelineContext
from app.core.embeddings import default_embedding_generator


class EmbeddingStage(PipelineStage):
    """
    Stage 4: Embedding Generation

    Generates vector embeddings for each chunk:
    - Uses default_embedding_generator (OpenAI by default)
    - Batches chunk processing for efficiency
    - Handles API errors gracefully
    - Stores embeddings as numpy arrays

    Input (from context):
        - chunks: List[SimpleChunk]

    Output (to context):
        - embeddings: List[np.ndarray]
    """

    @property
    def name(self) -> str:
        return "embedding"

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute embedding generation stage

        Args:
            context: Pipeline context with chunks

        Returns:
            StageResult indicating embedding generation success/failure
        """
        self.logger.info(f"🔢 Generating embeddings for {len(context.chunks) if context.chunks else 0} chunks")

        # Validate input
        error = self.validate_input(context, 'chunks')
        if error:
            return StageResult(
                success=False,
                stage_name=self.name,
                error=error
            )

        # Check if chunks exist
        if not context.chunks or len(context.chunks) == 0:
            return StageResult(
                success=False,
                stage_name=self.name,
                error="No chunks to generate embeddings for"
            )

        try:
            # Extract chunk texts
            chunk_texts = [chunk.text for chunk in context.chunks]

            # Generate embeddings using default embedding generator
            # This will use OpenAI API by default (text-embedding-3-small)
            self.logger.info(f"📡 Calling embedding API for {len(chunk_texts)} chunks...")

            # Use generate_embeddings_batch for efficient batch processing
            embeddings = default_embedding_generator.generate_embeddings_batch(
                texts=chunk_texts,
                show_progress=True
            )

            # Validate embeddings
            if not embeddings or len(embeddings) != len(chunk_texts):
                return StageResult(
                    success=False,
                    stage_name=self.name,
                    error=f"Embedding generation failed: expected {len(chunk_texts)} embeddings, got {len(embeddings) if embeddings else 0}",
                    metadata={
                        "chunks_count": len(chunk_texts),
                        "embeddings_count": len(embeddings) if embeddings else 0
                    }
                )

            # Convert to numpy arrays for consistency
            embeddings_np = [
                np.array(embedding, dtype=np.float32) if not isinstance(embedding, np.ndarray)
                else embedding.astype(np.float32)
                for embedding in embeddings
            ]

            # Store embeddings in context
            context.embeddings = embeddings_np

            # Log embedding statistics
            self._log_embedding_stats(embeddings_np)

            # Update context stats
            context.stats['embeddings_generated'] = len(embeddings_np)
            context.stats['embedding_dimension'] = len(embeddings_np[0]) if embeddings_np else 0
            context.stats['embedding_model'] = default_embedding_generator.model_name

            # Success
            return StageResult(
                success=True,
                stage_name=self.name,
                message=f"✅ Generated {len(embeddings_np)} embeddings (dim={len(embeddings_np[0])})",
                metadata={
                    "embeddings_generated": len(embeddings_np),
                    "embedding_dimension": len(embeddings_np[0]) if embeddings_np else 0,
                    "embedding_model": default_embedding_generator.model_name,
                    "embedding_provider": "openai"  # Could be dynamic based on settings
                }
            )

        except Exception as e:
            self.logger.exception(f"Embedding generation error: {e}")

            # Check for common API errors
            error_msg = str(e).lower()
            if "api key" in error_msg or "unauthorized" in error_msg:
                error_detail = "OpenAI API key is missing or invalid. Check OPENAI_API_KEY in .env"
            elif "rate limit" in error_msg:
                error_detail = "OpenAI API rate limit exceeded. Please try again later."
            elif "timeout" in error_msg:
                error_detail = "OpenAI API request timed out. Please try again."
            else:
                error_detail = f"Failed to generate embeddings: {str(e)}"

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
        No rollback needed for embedding stage (stateless operation)

        Embeddings are generated via API call and not stored anywhere yet.
        """
        self.logger.info(f"[{self.name}] No rollback needed (stateless stage)")

    def _log_embedding_stats(self, embeddings: List[np.ndarray]) -> None:
        """
        Log detailed embedding statistics

        Args:
            embeddings: List of embedding vectors
        """
        self.logger.info(f"📊 Embedding Statistics:")
        self.logger.info(f"   Total Embeddings: {len(embeddings)}")

        if embeddings and len(embeddings) > 0:
            dimension = len(embeddings[0])
            self.logger.info(f"   Embedding Dimension: {dimension}")
            self.logger.info(f"   Embedding Model: {default_embedding_generator.model_name}")

            # Calculate statistics
            # Norm statistics (magnitude of vectors)
            norms = [np.linalg.norm(emb) for emb in embeddings]
            avg_norm = np.mean(norms)
            min_norm = np.min(norms)
            max_norm = np.max(norms)

            self.logger.info(f"   Vector Norms: avg={avg_norm:.4f}, min={min_norm:.4f}, max={max_norm:.4f}")

            # Memory usage
            total_size_mb = sum(emb.nbytes for emb in embeddings) / (1024 * 1024)
            self.logger.info(f"   Memory Usage: {total_size_mb:.2f} MB")
