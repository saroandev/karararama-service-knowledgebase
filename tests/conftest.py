"""
Pytest configuration and fixtures for OneDocs RAG system tests
"""
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any
import numpy as np
import json
from io import BytesIO

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Environment setup for testing
os.environ.setdefault("MILVUS_HOST", "localhost")
os.environ.setdefault("MILVUS_PORT", "19530")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("OPENAI_API_KEY", "test_key_123")
os.environ.setdefault("LLM_PROVIDER", "openai")


@pytest.fixture(scope="session")
def test_data_dir():
    """Test data directory fixture"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def temp_dir():
    """Temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_pdf_data():
    """Mock PDF data for testing"""
    return {
        "content": b"Mock PDF content for testing",
        "filename": "test_document.pdf",
        "pages": [
            {
                "page_number": 1,
                "text": "This is the first page of a test document. It contains sample text for testing purposes.",
                "metadata": {"page_number": 1}
            },
            {
                "page_number": 2, 
                "text": "This is the second page with different content. More text for comprehensive testing.",
                "metadata": {"page_number": 2}
            }
        ],
        "metadata": {
            "title": "Test Document",
            "file_size": 2048,
            "page_count": 2
        }
    }


@pytest.fixture 
def mock_document_chunks():
    """Mock document chunks for testing"""
    return [
        {
            "chunk_id": "test_doc_001_chunk_001",
            "document_id": "test_doc_001",
            "text": "This is the first chunk of text from the document.",
            "metadata": {"page_number": 1, "chunk_index": 0},
            "token_count": 12,
            "char_count": 54
        },
        {
            "chunk_id": "test_doc_001_chunk_002", 
            "document_id": "test_doc_001",
            "text": "This is the second chunk with different content.",
            "metadata": {"page_number": 1, "chunk_index": 1},
            "token_count": 10,
            "char_count": 48
        },
        {
            "chunk_id": "test_doc_001_chunk_003",
            "document_id": "test_doc_001", 
            "text": "Third chunk from the second page of the document.",
            "metadata": {"page_number": 2, "chunk_index": 2},
            "token_count": 11,
            "char_count": 50
        }
    ]


@pytest.fixture
def mock_embeddings():
    """Mock embeddings for testing"""
    np.random.seed(42)  # For reproducible tests
    embeddings = []
    for i in range(3):
        embedding = np.random.normal(0, 1, 384)
        embedding = embedding / np.linalg.norm(embedding)
        embeddings.append(embedding.tolist())
    return embeddings


@pytest.fixture
def mock_milvus_collection():
    """Mock Milvus collection for testing"""
    mock_collection = MagicMock()
    mock_collection.name = "test_collection"
    mock_collection.num_entities = 0
    mock_collection.schema = MagicMock()
    
    # Mock search results
    mock_search_result = MagicMock()
    mock_search_result.ids = [["id1", "id2", "id3"]]
    mock_search_result.distances = [[0.95, 0.88, 0.82]]
    mock_collection.search.return_value = [mock_search_result]
    
    return mock_collection


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client for testing"""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    mock_client.make_bucket.return_value = None
    mock_client.put_object.return_value = MagicMock()
    mock_client.get_object.return_value = MagicMock()
    return mock_client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    mock_client = MagicMock()
    
    # Mock embedding response
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [
        MagicMock(embedding=np.random.normal(0, 1, 1536).tolist())
    ]
    mock_client.embeddings.create.return_value = mock_embedding_response
    
    # Mock chat completion response
    mock_completion_response = MagicMock()
    mock_completion_response.choices = [
        MagicMock(message=MagicMock(content="This is a test response from the LLM."))
    ]
    mock_client.chat.completions.create.return_value = mock_completion_response
    
    return mock_client


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer model for testing"""
    mock_model = MagicMock()
    mock_model.encode.return_value = np.random.normal(0, 1, (3, 384))
    return mock_model


@pytest.fixture
def sample_queries():
    """Sample queries for testing"""
    return [
        "What is this document about?",
        "Can you summarize the main points?",
        "What are the key findings mentioned?",
        "How does the system work?",
        "What are the technical requirements?"
    ]


@pytest.fixture
def test_config():
    """Test configuration fixture"""
    return {
        "milvus": {
            "host": "localhost",
            "port": 19530,
            "collection": "test_collection"
        },
        "minio": {
            "endpoint": "localhost:9000",
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "bucket_docs": "test-docs",
            "bucket_chunks": "test-chunks"
        },
        "embedding": {
            "model": "intfloat/multilingual-e5-small",
            "dimension": 384
        },
        "chunking": {
            "chunk_size": 512,
            "chunk_overlap": 50
        }
    }


@pytest.fixture
def docker_services_available():
    """Check if Docker services are available"""
    import socket
    
    def is_port_open(host: str, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    milvus_available = is_port_open("localhost", 19530)
    minio_available = is_port_open("localhost", 9000)
    
    return {
        "milvus": milvus_available,
        "minio": minio_available,
        "all": milvus_available and minio_available
    }


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Cleanup test files after each test"""
    yield
    
    # Cleanup test output directory
    test_output = Path("test_output")
    if test_output.exists():
        for file in test_output.glob("test_*"):
            try:
                if file.is_file():
                    file.unlink()
                elif file.is_dir():
                    shutil.rmtree(file)
            except Exception:
                pass


# Skip markers for conditional testing
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "requires_docker: mark test as requiring Docker services")
    config.addinivalue_line("markers", "requires_gpu: mark test as requiring GPU")
    config.addinivalue_line("markers", "requires_internet: mark test as requiring internet connection")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers"""
    # Skip Docker tests if services not available
    import socket
    
    def is_docker_available():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            milvus_ok = sock.connect_ex(("localhost", 19530)) == 0
            sock.close()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            minio_ok = sock.connect_ex(("localhost", 9000)) == 0
            sock.close()
            return milvus_ok and minio_ok
        except Exception:
            return False
    
    if not is_docker_available():
        skip_docker = pytest.mark.skip(reason="Docker services not available")
        for item in items:
            if "requires_docker" in item.keywords or "docker" in item.keywords:
                item.add_marker(skip_docker)


# Test data creation helpers
@pytest.fixture
def create_test_pdf():
    """Create a test PDF file"""
    def _create_pdf(filename: str = "test.pdf", content: str = "Test PDF content") -> bytes:
        # This would normally create a real PDF, but for testing we'll use mock data
        return f"Mock PDF: {content}".encode('utf-8')
    return _create_pdf


@pytest.fixture
def assert_embeddings_valid():
    """Helper to validate embeddings"""
    def _validate(embeddings: List[List[float]], expected_dim: int = 384):
        assert isinstance(embeddings, list), "Embeddings should be a list"
        assert len(embeddings) > 0, "Embeddings list should not be empty"
        
        for i, emb in enumerate(embeddings):
            assert isinstance(emb, list), f"Embedding {i} should be a list"
            assert len(emb) == expected_dim, f"Embedding {i} should have {expected_dim} dimensions"
            assert all(isinstance(x, (int, float)) for x in emb), f"Embedding {i} should contain only numbers"
            
            # Check if embedding is normalized (approximately)
            norm = np.linalg.norm(emb)
            assert 0.9 <= norm <= 1.1, f"Embedding {i} should be approximately normalized (norm={norm})"
            
    return _validate


@pytest.fixture
def assert_chunks_valid():
    """Helper to validate document chunks"""
    def _validate(chunks: List[Dict[str, Any]]):
        assert isinstance(chunks, list), "Chunks should be a list"
        assert len(chunks) > 0, "Chunks list should not be empty"
        
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, dict), f"Chunk {i} should be a dictionary"
            
            required_fields = ["chunk_id", "text", "metadata"]
            for field in required_fields:
                assert field in chunk, f"Chunk {i} should have field '{field}'"
                
            assert isinstance(chunk["text"], str), f"Chunk {i} text should be a string"
            assert len(chunk["text"]) > 0, f"Chunk {i} should have non-empty text"
            assert isinstance(chunk["metadata"], dict), f"Chunk {i} metadata should be a dict"
            
    return _validate