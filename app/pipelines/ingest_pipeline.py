"""
Document ingestion pipeline implementation
"""
import logging
import io
from typing import Dict, Any, Optional, List, BinaryIO
from datetime import datetime

from app.pipelines.base import AbstractPipeline, PipelineResult, PipelineStage
from app.core.storage import storage
from app.core.parsing import default_parser as pdf_parser
from app.core.chunking import get_default_chunker, HybridChunker, TextChunker
from app.core.embeddings import default_embedding_generator as embedding_generator
from app.core.indexing import default_indexer as milvus_indexer
from app.config import settings

logger = logging.getLogger(__name__)


class IngestPipeline(AbstractPipeline):
    """
    Pipeline for ingesting documents into the RAG system

    Stages:
    1. Store document in MinIO
    2. Parse document (PDF to text)
    3. Chunk text
    4. Generate embeddings
    5. Store in vector database
    6. Update metadata
    """

    def __init__(self):
        super().__init__(name="IngestPipeline")

        # Initialize components
        self.storage = storage
        self.parser = pdf_parser
        self.chunker = get_default_chunker()
        self.embedder = embedding_generator
        self.indexer = milvus_indexer

        # Pipeline configuration
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP
        self.chunk_strategy = settings.CHUNKING_STRATEGY

    def validate_inputs(self, **kwargs) -> bool:
        """
        Validate ingestion inputs

        Required kwargs:
            - file_obj or file_path: File to ingest
            - filename: Original filename

        Optional kwargs:
            - metadata: Additional metadata
            - chunk_size: Override chunk size
            - chunk_overlap: Override chunk overlap
            - chunk_strategy: Override chunking strategy
        """
        # Check for file input
        if not kwargs.get('file_obj') and not kwargs.get('file_path'):
            raise ValueError("Either 'file_obj' or 'file_path' must be provided")

        # Check filename
        if not kwargs.get('filename'):
            raise ValueError("'filename' is required")

        # Validate file extension
        filename = kwargs.get('filename', '')
        if not filename.lower().endswith('.pdf'):
            raise ValueError(f"Only PDF files are supported, got: {filename}")

        return True

    async def execute(self, **kwargs) -> PipelineResult:
        """
        Execute the ingestion pipeline

        Args:
            file_obj: File object to ingest (BinaryIO)
            file_path: Path to file (alternative to file_obj)
            filename: Original filename
            metadata: Additional metadata dict
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            chunk_strategy: Override default strategy

        Returns:
            PipelineResult with document_id and statistics
        """
        try:
            # Extract parameters
            file_obj = kwargs.get('file_obj')
            file_path = kwargs.get('file_path')
            filename = kwargs.get('filename')
            metadata = kwargs.get('metadata', {})
            chunk_size = kwargs.get('chunk_size', self.chunk_size)
            chunk_overlap = kwargs.get('chunk_overlap', self.chunk_overlap)
            chunk_strategy = kwargs.get('chunk_strategy', self.chunk_strategy)

            # Add ingestion timestamp to metadata
            metadata['ingested_at'] = datetime.now().isoformat()
            metadata['chunk_strategy'] = chunk_strategy
            metadata['chunk_size'] = chunk_size
            metadata['chunk_overlap'] = chunk_overlap

            # Stage 1: Store document in MinIO
            self.update_progress(
                "storing",
                20.0,
                f"Storing document: {filename}",
                1, 6
            )

            # Read file content if path provided
            if file_path and not file_obj:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                file_obj = io.BytesIO(file_content)

            # Store document
            document_id = self.storage.store_document(
                file_obj,
                filename,
                metadata
            )

            self.current_progress.metadata = {"document_id": document_id}

            # Stage 2: Parse PDF
            self.update_progress(
                "parsing",
                35.0,
                f"Parsing PDF: {filename}",
                2, 6
            )

            # Get document back from storage for parsing
            doc_content = self.storage.get_document(document_id)
            pages = self.parser.parse(io.BytesIO(doc_content), document_id)

            if not pages:
                raise ValueError("No content extracted from PDF")

            # Stage 3: Chunk text
            self.update_progress(
                "chunking",
                45.0,
                f"Creating chunks with {chunk_strategy} strategy",
                3, 6
            )

            if chunk_strategy == "hybrid":
                chunker = HybridChunker(chunk_size, chunk_overlap)
                chunks = chunker.chunk_text(
                    "\n\n".join(page.text for page in pages),
                    document_id,
                    metadata
                )
            else:
                chunker = TextChunker(chunk_size, chunk_overlap, chunk_strategy)
                chunks = chunker.chunk_pages(pages, document_id, preserve_pages=True)

            if not chunks:
                raise ValueError("No chunks created from text")

            num_chunks = len(chunks)
            self.logger.info(f"Created {num_chunks} chunks")

            # Stage 4: Generate embeddings
            self.update_progress(
                "embedding",
                60.0,
                f"Generating embeddings for {num_chunks} chunks",
                4, 6
            )

            texts = [chunk.text for chunk in chunks]
            embeddings = self.embedder.generate_embeddings_batch(
                texts,
                show_progress=True
            )

            # Stage 5: Store chunks and embeddings
            self.update_progress(
                "indexing",
                80.0,
                f"Storing {num_chunks} chunks in vector database",
                5, 6
            )

            # Store chunks in MinIO
            chunk_metadata = []
            for i, chunk in enumerate(chunks):
                chunk_data = {
                    "chunk_id": chunk.id,
                    "text": chunk.text,
                    "chunk_index": i,
                    "page_numbers": chunk.page_numbers,
                    "token_count": chunk.token_count,
                    "char_count": len(chunk.text),
                    "metadata": chunk.metadata
                }
                chunk_metadata.append(chunk_data)

            minio_paths = self.storage.store_chunks(chunk_metadata, document_id)

            # Prepare data for Milvus
            chunks_for_milvus = []
            for i, chunk in enumerate(chunks):
                chunk_dict = {
                    "id": chunk.id,
                    "chunk_text": chunk.text[:65535],  # Milvus VARCHAR limit
                    "document_id": document_id,
                    "page_number": chunk.page_numbers[0] if chunk.page_numbers else 0,
                    "chunk_index": i,
                    "metadata": {
                        "document_title": metadata.get("document_title", filename),
                        "chunk_id": chunk.id,
                        "page_numbers": chunk.page_numbers,
                        "token_count": chunk.token_count,
                        "created_at": datetime.now().timestamp(),
                        "minio_object_path": minio_paths[i] if i < len(minio_paths) else None
                    }
                }
                chunks_for_milvus.append(chunk_dict)

            # Insert into Milvus
            num_indexed = self.indexer.insert_chunks(chunks_for_milvus, embeddings)

            # Stage 6: Update document metadata
            self.update_progress(
                "finalizing",
                95.0,
                "Updating document metadata",
                6, 6
            )

            # Update document metadata with chunk info
            self.storage.update_document_metadata(document_id, {
                "num_chunks": num_chunks,
                "num_pages": len(pages),
                "indexed_chunks": num_indexed,
                "processing_completed": datetime.now().isoformat()
            })

            # Return success result
            return PipelineResult(
                success=True,
                data={
                    "document_id": document_id,
                    "filename": filename,
                    "num_pages": len(pages),
                    "num_chunks": num_chunks,
                    "num_indexed": num_indexed,
                    "metadata": metadata
                }
            )

        except Exception as e:
            error_msg = f"Ingestion failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            # Try to clean up if document was created
            if 'document_id' in locals():
                try:
                    self.storage.delete_document(document_id)
                    self.indexer.delete_by_document(document_id)
                except:
                    pass

            return PipelineResult(
                success=False,
                error=error_msg
            )


class BatchIngestPipeline(AbstractPipeline):
    """Pipeline for ingesting multiple documents"""

    def __init__(self):
        super().__init__(name="BatchIngestPipeline")
        self.single_ingest = IngestPipeline()

    def validate_inputs(self, **kwargs) -> bool:
        """Validate batch ingestion inputs"""
        if not kwargs.get('files'):
            raise ValueError("'files' list is required")

        files = kwargs.get('files', [])
        if not files:
            raise ValueError("'files' list cannot be empty")

        for file_info in files:
            if not file_info.get('file_obj') and not file_info.get('file_path'):
                raise ValueError("Each file must have 'file_obj' or 'file_path'")
            if not file_info.get('filename'):
                raise ValueError("Each file must have 'filename'")

        return True

    async def execute(self, **kwargs) -> PipelineResult:
        """
        Execute batch ingestion

        Args:
            files: List of file dictionaries with keys:
                - file_obj or file_path
                - filename
                - metadata (optional)

        Returns:
            PipelineResult with all document results
        """
        files = kwargs.get('files', [])
        total_files = len(files)
        results = []
        successful = 0
        failed = 0

        for i, file_info in enumerate(files):
            # Check if cancelled
            if self.is_cancelled:
                break

            # Update progress
            self.update_progress(
                "processing",
                (i / total_files) * 90 + 10,
                f"Processing file {i+1}/{total_files}: {file_info.get('filename')}",
                i + 1,
                total_files
            )

            # Ingest single file
            result = await self.single_ingest.run(**file_info)
            results.append({
                "filename": file_info.get('filename'),
                "success": result.success,
                "data": result.data if result.success else None,
                "error": result.error if not result.success else None
            })

            if result.success:
                successful += 1
            else:
                failed += 1

        # Return batch result
        return PipelineResult(
            success=failed == 0,
            data={
                "total_files": total_files,
                "successful": successful,
                "failed": failed,
                "results": results
            }
        )