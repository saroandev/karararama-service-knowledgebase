"""
Test utilities and helper functions
"""
import os
import socket
import time
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np
from unittest.mock import MagicMock


def is_port_open(host: str, port: int, timeout: float = 5.0) -> bool:
    """
    Check if a port is open on a given host
    
    Args:
        host: The hostname or IP address
        port: The port number to check
        timeout: Timeout in seconds
        
    Returns:
        True if port is open, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def wait_for_service(host: str, port: int, max_attempts: int = 30, delay: float = 1.0) -> bool:
    """
    Wait for a service to become available
    
    Args:
        host: The hostname or IP address
        port: The port number to check
        max_attempts: Maximum number of attempts
        delay: Delay between attempts in seconds
        
    Returns:
        True if service becomes available, False if timeout
    """
    for attempt in range(max_attempts):
        if is_port_open(host, port):
            return True
        time.sleep(delay)
    return False


def check_docker_services() -> Dict[str, bool]:
    """
    Check availability of Docker services
    
    Returns:
        Dictionary with service availability status
    """
    services = {
        "milvus": is_port_open("localhost", 19530),
        "minio": is_port_open("localhost", 9000),
        "etcd": is_port_open("localhost", 2379)
    }
    services["all"] = all(services.values())
    return services


def create_test_pdf_content(title: str = "Test Document", pages: int = 3) -> bytes:
    """
    Create mock PDF content for testing
    
    Args:
        title: Document title
        pages: Number of pages to simulate
        
    Returns:
        Mock PDF content as bytes
    """
    content = f"Mock PDF Document: {title}\n"
    content += f"Total Pages: {pages}\n\n"
    
    for page_num in range(1, pages + 1):
        content += f"Page {page_num}\n"
        content += f"This is page {page_num} of the test document. "
        content += f"It contains sample text for testing the RAG pipeline functionality. "
        content += f"Each page has unique content to test chunking and retrieval.\n\n"
    
    return content.encode('utf-8')


def generate_mock_embeddings(count: int, dimension: int = 384, seed: Optional[int] = None) -> List[List[float]]:
    """
    Generate mock embeddings for testing
    
    Args:
        count: Number of embeddings to generate
        dimension: Dimension of each embedding
        seed: Random seed for reproducibility
        
    Returns:
        List of normalized embeddings
    """
    if seed is not None:
        np.random.seed(seed)
    
    embeddings = []
    for i in range(count):
        # Generate random embedding
        embedding = np.random.normal(0, 1, dimension)
        # Normalize to unit vector
        embedding = embedding / np.linalg.norm(embedding)
        embeddings.append(embedding.tolist())
    
    return embeddings


def create_mock_chunks(document_id: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Create mock document chunks for testing
    
    Args:
        document_id: Document identifier
        count: Number of chunks to create
        
    Returns:
        List of mock chunks
    """
    chunks = []
    for i in range(count):
        chunk = {
            "chunk_id": f"{document_id}_chunk_{i:03d}",
            "document_id": document_id,
            "text": f"This is chunk {i+1} of the test document. It contains sample text for testing purposes.",
            "metadata": {
                "page_number": (i // 2) + 1,  # 2 chunks per page
                "chunk_index": i,
                "section": f"section_{i % 3 + 1}"
            },
            "token_count": 20 + (i * 2),  # Variable token count
            "char_count": 80 + (i * 10)   # Variable character count
        }
        chunks.append(chunk)
    
    return chunks


def validate_chunk_structure(chunks: List[Dict[str, Any]]) -> bool:
    """
    Validate that chunks have the correct structure
    
    Args:
        chunks: List of chunks to validate
        
    Returns:
        True if all chunks are valid, False otherwise
    """
    required_fields = ["chunk_id", "document_id", "text", "metadata"]
    
    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            print(f"Chunk {i} is not a dictionary")
            return False
        
        for field in required_fields:
            if field not in chunk:
                print(f"Chunk {i} missing required field: {field}")
                return False
        
        if not isinstance(chunk["text"], str) or len(chunk["text"]) == 0:
            print(f"Chunk {i} has invalid text field")
            return False
        
        if not isinstance(chunk["metadata"], dict):
            print(f"Chunk {i} has invalid metadata field")
            return False
    
    return True


def validate_embeddings(embeddings: List[List[float]], expected_dim: int = 384) -> bool:
    """
    Validate that embeddings have the correct structure and properties
    
    Args:
        embeddings: List of embeddings to validate
        expected_dim: Expected dimension of each embedding
        
    Returns:
        True if all embeddings are valid, False otherwise
    """
    if not isinstance(embeddings, list):
        print("Embeddings should be a list")
        return False
    
    for i, emb in enumerate(embeddings):
        if not isinstance(emb, list):
            print(f"Embedding {i} should be a list")
            return False
        
        if len(emb) != expected_dim:
            print(f"Embedding {i} has dimension {len(emb)}, expected {expected_dim}")
            return False
        
        if not all(isinstance(x, (int, float)) for x in emb):
            print(f"Embedding {i} contains non-numeric values")
            return False
        
        # Check if normalized (approximately)
        norm = np.linalg.norm(emb)
        if not (0.9 <= norm <= 1.1):
            print(f"Embedding {i} is not normalized (norm={norm})")
            return False
    
    return True


def create_temporary_config(overrides: Dict[str, str]) -> Path:
    """
    Create a temporary configuration file for testing
    
    Args:
        overrides: Configuration values to override
        
    Returns:
        Path to temporary config file
    """
    config_content = []
    
    for key, value in overrides.items():
        config_content.append(f"{key}={value}")
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False)
    temp_file.write('\n'.join(config_content))
    temp_file.close()
    
    return Path(temp_file.name)


def cleanup_temp_files(file_paths: List[Path]):
    """
    Clean up temporary files created during tests
    
    Args:
        file_paths: List of file paths to clean up
    """
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            print(f"Failed to cleanup {file_path}: {e}")


def save_test_results(results: Dict[str, Any], output_dir: str = "test_output") -> Path:
    """
    Save test results to JSON file
    
    Args:
        results: Test results dictionary
        output_dir: Output directory for results
        
    Returns:
        Path to saved results file
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = output_path / f"test_results_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    return results_file


def compare_embeddings(emb1: List[float], emb2: List[float], threshold: float = 0.01) -> bool:
    """
    Compare two embeddings for similarity (useful for testing consistency)
    
    Args:
        emb1: First embedding
        emb2: Second embedding
        threshold: Maximum allowed difference
        
    Returns:
        True if embeddings are similar, False otherwise
    """
    if len(emb1) != len(emb2):
        return False
    
    diff = np.abs(np.array(emb1) - np.array(emb2))
    max_diff = np.max(diff)
    
    return max_diff <= threshold


def mock_api_response(status_code: int = 200, data: Optional[Dict[str, Any]] = None) -> MagicMock:
    """
    Create mock API response for testing
    
    Args:
        status_code: HTTP status code
        data: Response data
        
    Returns:
        Mock response object
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = data or {}
    return mock_response


def assert_response_structure(response_data: Dict[str, Any], required_fields: List[str]):
    """
    Assert that a response has the required structure
    
    Args:
        response_data: Response data to validate
        required_fields: List of required fields
        
    Raises:
        AssertionError: If structure is invalid
    """
    assert isinstance(response_data, dict), "Response should be a dictionary"
    
    for field in required_fields:
        assert field in response_data, f"Response missing required field: {field}"


def benchmark_function(func, *args, **kwargs) -> Dict[str, Any]:
    """
    Benchmark a function's execution time and memory usage
    
    Args:
        func: Function to benchmark
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Benchmark results
    """
    import psutil
    import gc
    
    # Measure memory before
    gc.collect()
    process = psutil.Process()
    memory_before = process.memory_info().rss / 1024 / 1024  # MB
    
    # Measure execution time
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    
    # Measure memory after
    gc.collect()
    memory_after = process.memory_info().rss / 1024 / 1024  # MB
    
    return {
        "execution_time": end_time - start_time,
        "memory_before_mb": memory_before,
        "memory_after_mb": memory_after,
        "memory_delta_mb": memory_after - memory_before,
        "result": result
    }


class TestDataGenerator:
    """Utility class for generating test data"""
    
    @staticmethod
    def create_document_metadata(title: str = "Test Document") -> Dict[str, Any]:
        """Create document metadata for testing"""
        return {
            "title": title,
            "author": "Test Author",
            "created_date": "2024-01-01",
            "file_size": 2048,
            "page_count": 3,
            "document_type": "pdf"
        }
    
    @staticmethod
    def create_query_response(question: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create query response for testing"""
        return {
            "success": True,
            "question": question,
            "answer": f"This is a test answer for: {question}",
            "sources": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"][:100] + "..." if len(chunk["text"]) > 100 else chunk["text"],
                    "score": 0.95 - (i * 0.1),
                    "metadata": chunk["metadata"]
                }
                for i, chunk in enumerate(chunks[:3])  # Top 3 results
            ],
            "processing_time": 1.23
        }
    
    @staticmethod
    def create_error_response(error_msg: str, error_code: str = "TEST_ERROR") -> Dict[str, Any]:
        """Create error response for testing"""
        return {
            "success": False,
            "error": error_msg,
            "error_code": error_code,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }