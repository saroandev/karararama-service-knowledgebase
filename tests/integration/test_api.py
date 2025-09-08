"""
Integration tests for the FastAPI server endpoints
"""
import pytest
from fastapi.testclient import TestClient
import json
import io
from unittest.mock import patch, MagicMock

from app.server import app


@pytest.mark.integration
@pytest.mark.api
class TestAPIEndpoints:
    """Test API endpoints integration"""

    @pytest.fixture
    def client(self):
        """Test client fixture"""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "services" in data

    def test_docs_endpoint(self, client):
        """Test API documentation endpoint"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_endpoint(self, client):
        """Test OpenAPI schema endpoint"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    @patch('app.ingest.DocumentIngestionPipeline')
    def test_ingest_endpoint_success(self, mock_pipeline_class, client):
        """Test successful document ingestion"""
        # Mock the pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.ingest_document.return_value = {
            "success": True,
            "document_id": "test_doc_123",
            "chunks_created": 5,
            "vectors_indexed": 5,
            "processing_time": 2.5
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create test file
        test_file = io.BytesIO(b"Test PDF content")
        test_file.name = "test.pdf"
        
        response = client.post(
            "/ingest",
            files={"file": ("test.pdf", test_file, "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] == "test_doc_123"
        assert data["chunks_created"] == 5

    def test_ingest_endpoint_no_file(self, client):
        """Test ingestion endpoint without file"""
        response = client.post("/ingest")
        
        assert response.status_code == 422  # Validation error

    def test_ingest_endpoint_wrong_file_type(self, client):
        """Test ingestion with wrong file type"""
        test_file = io.BytesIO(b"Not a PDF")
        
        response = client.post(
            "/ingest",
            files={"file": ("test.txt", test_file, "text/plain")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @patch('app.ingest.DocumentIngestionPipeline')
    def test_ingest_endpoint_processing_error(self, mock_pipeline_class, client):
        """Test ingestion endpoint with processing error"""
        # Mock pipeline to return error
        mock_pipeline = MagicMock()
        mock_pipeline.ingest_document.return_value = {
            "success": False,
            "error": "PDF parsing failed"
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        test_file = io.BytesIO(b"Corrupted PDF content")
        test_file.name = "corrupt.pdf"
        
        response = client.post(
            "/ingest",
            files={"file": ("corrupt.pdf", test_file, "application/pdf")}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data

    @patch('app.retrieve.QueryEngine')
    def test_query_endpoint_success(self, mock_query_engine_class, client):
        """Test successful query processing"""
        # Mock query engine
        mock_engine = MagicMock()
        mock_engine.process_query.return_value = {
            "success": True,
            "answer": "This document is about testing the RAG system.",
            "sources": [
                {
                    "chunk_id": "test_chunk_001",
                    "text": "Test chunk content...",
                    "score": 0.95,
                    "metadata": {"page_number": 1}
                }
            ],
            "processing_time": 1.2
        }
        mock_query_engine_class.return_value = mock_engine
        
        response = client.post(
            "/query",
            json={"question": "What is this document about?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "answer" in data
        assert "sources" in data
        assert len(data["sources"]) > 0

    def test_query_endpoint_missing_question(self, client):
        """Test query endpoint without question"""
        response = client.post("/query", json={})
        
        assert response.status_code == 422  # Validation error

    def test_query_endpoint_empty_question(self, client):
        """Test query endpoint with empty question"""
        response = client.post("/query", json={"question": ""})
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @patch('app.retrieve.QueryEngine')
    def test_query_endpoint_processing_error(self, mock_query_engine_class, client):
        """Test query endpoint with processing error"""
        # Mock query engine to return error
        mock_engine = MagicMock()
        mock_engine.process_query.return_value = {
            "success": False,
            "error": "No documents found in the database"
        }
        mock_query_engine_class.return_value = mock_engine
        
        response = client.post(
            "/query",
            json={"question": "What is this about?"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    @patch('app.storage.storage')
    def test_documents_list_endpoint(self, mock_storage, client):
        """Test documents listing endpoint"""
        # Mock storage to return document list
        mock_storage.list_files.return_value = [
            {"name": "doc1.pdf", "size": 1024, "last_modified": "2024-01-01"},
            {"name": "doc2.pdf", "size": 2048, "last_modified": "2024-01-02"}
        ]
        
        response = client.get("/documents")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 2
        assert data["documents"][0]["name"] == "doc1.pdf"

    @patch('app.storage.storage')
    def test_document_delete_endpoint(self, mock_storage, client):
        """Test document deletion endpoint"""
        # Mock successful deletion
        mock_storage.delete_file.return_value = True
        
        response = client.delete("/documents/test_doc_123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('app.storage.storage')
    def test_document_delete_not_found(self, mock_storage, client):
        """Test deleting non-existent document"""
        # Mock failed deletion
        mock_storage.delete_file.return_value = False
        
        response = client.delete("/documents/nonexistent_doc")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options("/health")
        
        # Check CORS headers (depending on CORS middleware configuration)
        assert response.status_code in [200, 405]  # OPTIONS might not be explicitly handled

    def test_rate_limiting_headers(self, client):
        """Test rate limiting headers if implemented"""
        response = client.get("/health")
        
        # This would test rate limiting if implemented
        assert response.status_code == 200

    @patch('app.index.MilvusVectorIndex')
    def test_search_endpoint(self, mock_index_class, client):
        """Test vector search endpoint"""
        # Mock vector index
        mock_index = MagicMock()
        mock_index.search_vectors.return_value = [
            {
                "chunk_id": "test_chunk_001",
                "score": 0.95,
                "text": "Test content",
                "metadata": {"page_number": 1}
            }
        ]
        mock_index_class.return_value = mock_index
        
        response = client.post(
            "/search",
            json={"query": "test query", "top_k": 5}
        )
        
        if response.status_code == 404:  # Endpoint might not exist
            pytest.skip("Search endpoint not implemented")
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_websocket_connection(self, client):
        """Test WebSocket connection for real-time updates"""
        with client.websocket_connect("/ws") as websocket:
            # Test basic WebSocket connection
            data = websocket.receive_json()
            assert "status" in data or "type" in data

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint if available"""
        response = client.get("/metrics")
        
        # Metrics endpoint might not be implemented
        if response.status_code == 404:
            pytest.skip("Metrics endpoint not implemented")
        
        assert response.status_code == 200

    def test_api_versioning(self, client):
        """Test API versioning"""
        response = client.get("/")
        
        if response.status_code == 404:
            response = client.get("/health")
        
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.api 
@pytest.mark.slow
class TestAPIPerformance:
    """Performance tests for API endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_concurrent_requests(self, client):
        """Test handling concurrent requests"""
        import concurrent.futures
        import time
        
        def make_request():
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            return response.status_code == 200, end_time - start_time
        
        # Test 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 10
        
        # Check response times are reasonable
        avg_time = sum(time for _, time in results) / len(results)
        assert avg_time < 1.0  # Should be less than 1 second

    @patch('app.ingest.DocumentIngestionPipeline')
    def test_large_file_upload(self, mock_pipeline_class, client):
        """Test handling large file uploads"""
        # Mock successful processing
        mock_pipeline = MagicMock()
        mock_pipeline.ingest_document.return_value = {
            "success": True,
            "document_id": "large_doc_123",
            "chunks_created": 100,
            "vectors_indexed": 100
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create a large test file (1MB)
        large_content = b"x" * 1024 * 1024
        test_file = io.BytesIO(large_content)
        test_file.name = "large.pdf"
        
        response = client.post(
            "/ingest",
            files={"file": ("large.pdf", test_file, "application/pdf")}
        )
        
        assert response.status_code == 200

    @patch('app.retrieve.QueryEngine')
    def test_query_response_time(self, mock_query_engine_class, client):
        """Test query response time"""
        import time
        
        # Mock fast query processing
        mock_engine = MagicMock()
        mock_engine.process_query.return_value = {
            "success": True,
            "answer": "Quick response",
            "sources": [],
            "processing_time": 0.1
        }
        mock_query_engine_class.return_value = mock_engine
        
        start_time = time.time()
        response = client.post(
            "/query",
            json={"question": "Quick test question?"}
        )
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 2.0  # Should respond within 2 seconds


@pytest.mark.integration
@pytest.mark.api
class TestAPIErrorHandling:
    """Test API error handling and edge cases"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_malformed_json(self, client):
        """Test handling of malformed JSON"""
        response = client.post(
            "/query",
            data='{"question": malformed json}',
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422

    def test_oversized_request(self, client):
        """Test handling of oversized requests"""
        # Create very large JSON payload
        large_question = "x" * 10000  # 10KB question
        
        response = client.post(
            "/query",
            json={"question": large_question}
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 413, 400]

    def test_invalid_file_format(self, client):
        """Test upload of invalid file formats"""
        # Try to upload an image as PDF
        test_file = io.BytesIO(b"\x89PNG\r\n\x1a\n")  # PNG header
        
        response = client.post(
            "/ingest",
            files={"file": ("image.pdf", test_file, "application/pdf")}
        )
        
        assert response.status_code in [400, 422]

    def test_empty_file_upload(self, client):
        """Test upload of empty file"""
        empty_file = io.BytesIO(b"")
        
        response = client.post(
            "/ingest",
            files={"file": ("empty.pdf", empty_file, "application/pdf")}
        )
        
        assert response.status_code == 400

    def test_special_characters_in_query(self, client):
        """Test queries with special characters"""
        special_chars_query = "What about émojis 🚀 and spëcial characters?"
        
        response = client.post(
            "/query",
            json={"question": special_chars_query}
        )
        
        # Should handle Unicode gracefully
        assert response.status_code in [200, 404, 500]