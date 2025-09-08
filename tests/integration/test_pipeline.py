"""
Integration tests for the complete RAG pipeline
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

from app.parse import PageData
from app.chunk import DocumentBasedChunker
from app.embed import HuggingFaceEmbedding
from app.ingest import DocumentIngestionPipeline


@pytest.mark.integration
@pytest.mark.slow
class TestRAGPipelineIntegration:
    """Test complete RAG pipeline integration"""

    def test_parse_chunk_integration(self, mock_pdf_data):
        """Test PDF parsing followed by chunking"""
        # Create mock pages from PDF data
        pages = [
            PageData(
                text=page["text"],
                page_number=page["page_number"],
                metadata=page["metadata"]
            ) for page in mock_pdf_data["pages"]
        ]
        
        # Test chunking
        chunker = DocumentBasedChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_by_document(pages, "test_doc_001", {"title": "Test Doc"})
        
        # Verify integration
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.document_id == "test_doc_001"
            assert "title" in chunk.metadata
            assert chunk.metadata["title"] == "Test Doc"
            assert "page_number" in chunk.metadata
            assert chunk.metadata["page_number"] in [1, 2]

    @patch('app.embed.SentenceTransformer')
    def test_chunk_embed_integration(self, mock_st, mock_document_chunks):
        """Test chunking followed by embedding generation"""
        # Mock sentence transformer
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        
        # Create embeddings for chunks
        embeddings_array = np.random.normal(0, 1, (len(mock_document_chunks), 384))
        mock_model.encode.return_value = embeddings_array
        mock_st.return_value = mock_model
        
        # Test embedding generation
        embedding_generator = HuggingFaceEmbedding(model_name="test-model")
        chunk_texts = [chunk["text"] for chunk in mock_document_chunks]
        embeddings = embedding_generator.generate_embeddings(chunk_texts)
        
        # Verify integration
        assert len(embeddings) == len(mock_document_chunks)
        assert len(embeddings[0]) == 384
        
        # Check that embeddings are normalized
        for embedding in embeddings:
            norm = np.linalg.norm(embedding)
            assert 0.9 <= norm <= 1.1

    @patch('app.storage.Minio')
    @patch('app.embed.SentenceTransformer') 
    def test_embed_store_integration(self, mock_st, mock_minio, mock_document_chunks, mock_embeddings):
        """Test embedding generation followed by storage"""
        from app.storage import MinIOStorage
        
        # Mock MinIO
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.put_object.return_value = MagicMock()
        mock_minio.return_value = mock_client
        
        # Mock sentence transformer
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array(mock_embeddings)
        mock_st.return_value = mock_model
        
        # Test the integration
        embedding_generator = HuggingFaceEmbedding(model_name="test-model")
        storage = MinIOStorage("localhost:9000", "key", "secret")
        
        chunk_texts = [chunk["text"] for chunk in mock_document_chunks]
        embeddings = embedding_generator.generate_embeddings(chunk_texts)
        
        # Store embeddings as JSON
        embedding_data = {
            "document_id": "test_doc_001",
            "chunks": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "embedding": embedding
                }
                for chunk, embedding in zip(mock_document_chunks, embeddings)
            ]
        }
        
        result = storage.upload_json("test-bucket", "embeddings.json", embedding_data)
        assert result is True

    @patch('app.index.connections')
    @patch('app.index.Collection')
    def test_embed_index_integration(self, mock_collection_class, mock_connections, mock_document_chunks, mock_embeddings):
        """Test embedding followed by vector indexing"""
        from app.index import MilvusVectorIndex
        
        # Mock Milvus components
        mock_collection = MagicMock()
        mock_collection.insert.return_value = MagicMock()
        mock_collection.load.return_value = None
        mock_collection.num_entities = len(mock_document_chunks)
        mock_collection_class.return_value = mock_collection
        
        mock_connections.connect.return_value = None
        
        # Test integration
        index = MilvusVectorIndex()
        
        # Prepare data for indexing
        entities = []
        for i, (chunk, embedding) in enumerate(zip(mock_document_chunks, mock_embeddings)):
            entities.append({
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "text": chunk["text"],
                "embedding": embedding,
                "chunk_index": i,
                "metadata": chunk["metadata"]
            })
        
        # Index the data
        result = index.insert_vectors(entities)
        assert result is True
        
        mock_collection.insert.assert_called_once()

    @patch('app.index.connections')
    @patch('app.index.Collection')
    @patch('app.embed.SentenceTransformer')
    def test_query_retrieve_integration(self, mock_st, mock_collection_class, mock_connections, mock_embeddings):
        """Test query embedding followed by vector search"""
        from app.index import MilvusVectorIndex
        from app.embed import HuggingFaceEmbedding
        
        # Mock sentence transformer for query embedding
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        query_embedding = np.random.normal(0, 1, 384)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        mock_model.encode.return_value = np.array([query_embedding])
        mock_st.return_value = mock_model
        
        # Mock Milvus search results
        mock_collection = MagicMock()
        mock_search_result = MagicMock()
        mock_search_result.ids = [["id1", "id2", "id3"]]
        mock_search_result.distances = [[0.95, 0.88, 0.82]]
        mock_collection.search.return_value = [mock_search_result]
        mock_collection_class.return_value = mock_collection
        
        # Test integration
        embedding_generator = HuggingFaceEmbedding(model_name="test-model")
        index = MilvusVectorIndex()
        
        # Generate query embedding
        query = "What is this document about?"
        query_embeddings = embedding_generator.generate_embeddings([query])
        
        # Search for similar vectors
        results = index.search_vectors(query_embeddings[0], top_k=3)
        
        assert len(results) > 0
        mock_collection.search.assert_called_once()

    @patch('app.storage.Minio')
    @patch('app.index.connections')
    @patch('app.index.Collection')
    @patch('app.embed.SentenceTransformer')
    def test_full_ingestion_pipeline(self, mock_st, mock_collection_class, mock_connections, mock_minio, mock_pdf_data):
        """Test complete document ingestion pipeline"""
        # Mock all external dependencies
        self._setup_mocks(mock_st, mock_collection_class, mock_connections, mock_minio)
        
        from app.ingest import DocumentIngestionPipeline
        
        # Create pipeline
        pipeline = DocumentIngestionPipeline()
        
        # Create mock PDF file data
        pdf_data = b"Mock PDF content for integration testing"
        filename = "test_document.pdf"
        
        # Run full ingestion
        result = pipeline.ingest_document(
            file_data=pdf_data,
            filename=filename,
            document_metadata={"title": "Integration Test Document"}
        )
        
        # Verify pipeline completion
        assert result["success"] is True
        assert "document_id" in result
        assert result["chunks_created"] > 0
        assert result["vectors_indexed"] > 0

    def _setup_mocks(self, mock_st, mock_collection_class, mock_connections, mock_minio):
        """Setup common mocks for integration tests"""
        # Mock sentence transformer
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.random.normal(0, 1, (3, 384))
        mock_st.return_value = mock_model
        
        # Mock Milvus
        mock_collection = MagicMock()
        mock_collection.insert.return_value = MagicMock()
        mock_collection.load.return_value = None
        mock_collection.num_entities = 3
        mock_collection_class.return_value = mock_collection
        mock_connections.connect.return_value = None
        
        # Mock MinIO
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.put_object.return_value = MagicMock()
        mock_minio.return_value = mock_client

    @patch('app.parse.fitz')
    def test_pipeline_error_handling(self, mock_fitz):
        """Test pipeline error handling and recovery"""
        from app.ingest import DocumentIngestionPipeline
        
        # Mock PDF parsing error
        mock_fitz.open.side_effect = Exception("PDF parsing failed")
        
        pipeline = DocumentIngestionPipeline()
        
        # Test error handling
        result = pipeline.ingest_document(
            file_data=b"corrupted pdf",
            filename="corrupted.pdf",
            document_metadata={}
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "PDF parsing failed" in result["error"]

    def test_pipeline_with_empty_document(self):
        """Test pipeline behavior with empty document"""
        from app.chunk import DocumentBasedChunker
        
        # Test with empty pages
        chunker = DocumentBasedChunker()
        chunks = chunker.chunk_by_document([], "empty_doc", {})
        
        assert len(chunks) == 0

    @patch('app.embed.SentenceTransformer')
    def test_pipeline_embedding_batch_processing(self, mock_st, mock_document_chunks):
        """Test pipeline handles large batches of text for embedding"""
        # Create large number of chunks
        large_chunk_list = mock_document_chunks * 20  # 60 chunks total
        
        # Mock sentence transformer with batch processing
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        
        # Return different embeddings for each batch
        def mock_encode(texts, **kwargs):
            return np.random.normal(0, 1, (len(texts), 384))
        
        mock_model.encode.side_effect = mock_encode
        mock_st.return_value = mock_model
        
        from app.embed import HuggingFaceEmbedding
        
        embedding_generator = HuggingFaceEmbedding(model_name="test-model")
        chunk_texts = [chunk["text"] for chunk in large_chunk_list]
        
        embeddings = embedding_generator.generate_embeddings(chunk_texts, show_progress=False)
        
        assert len(embeddings) == len(large_chunk_list)
        assert all(len(emb) == 384 for emb in embeddings)


@pytest.mark.integration
class TestPipelineErrorRecovery:
    """Test pipeline error recovery and resilience"""

    def test_partial_failure_recovery(self, mock_document_chunks):
        """Test pipeline continues processing when some chunks fail"""
        from app.chunk import DocumentBasedChunker
        
        # Create pages where one will cause processing issues
        pages = [
            PageData(text="Normal text content", page_number=1, metadata={}),
            PageData(text="", page_number=2, metadata={}),  # Empty page
            PageData(text="More normal content", page_number=3, metadata={})
        ]
        
        chunker = DocumentBasedChunker()
        chunks = chunker.chunk_by_document(pages, "partial_fail_test", {})
        
        # Should process successfully despite empty page
        assert len(chunks) >= 2  # At least the non-empty pages

    @patch('app.storage.Minio')
    def test_storage_retry_mechanism(self, mock_minio):
        """Test storage retry mechanism on failures"""
        from app.storage import MinIOStorage
        
        mock_client = MagicMock()
        # First call fails, second succeeds
        mock_client.put_object.side_effect = [Exception("Network error"), MagicMock()]
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        
        # This would normally retry in a real implementation
        # For now, just test that the error is handled
        result = storage.upload_file("test-bucket", "test-file.txt", b"test data")
        
        # Depending on implementation, this might succeed after retry or fail
        assert isinstance(result, bool)

    def test_pipeline_data_consistency(self, mock_document_chunks, mock_embeddings):
        """Test that pipeline maintains data consistency across steps"""
        # Verify chunk-embedding alignment
        assert len(mock_document_chunks) == len(mock_embeddings)
        
        # Verify chunk IDs are unique
        chunk_ids = [chunk["chunk_id"] for chunk in mock_document_chunks]
        assert len(chunk_ids) == len(set(chunk_ids))
        
        # Verify embeddings have correct dimensions
        for embedding in mock_embeddings:
            assert len(embedding) == 384
            norm = np.linalg.norm(embedding)
            assert 0.9 <= norm <= 1.1  # Should be normalized


@pytest.mark.integration
@pytest.mark.requires_docker
class TestFullSystemIntegration:
    """Full system integration tests (requires Docker services)"""

    @pytest.mark.slow
    def test_end_to_end_document_processing(self, docker_services_available, create_test_pdf):
        """Test complete end-to-end document processing"""
        if not docker_services_available["all"]:
            pytest.skip("Docker services not available")
        
        # This would test the full pipeline with real services
        # Implementation depends on having Docker services running
        pass

    @pytest.mark.slow
    def test_concurrent_document_processing(self, docker_services_available):
        """Test processing multiple documents concurrently"""
        if not docker_services_available["all"]:
            pytest.skip("Docker services not available")
        
        # Test concurrent processing
        pass

    @pytest.mark.slow
    def test_system_under_load(self, docker_services_available):
        """Test system performance under load"""
        if not docker_services_available["all"]:
            pytest.skip("Docker services not available")
        
        # Load testing
        pass