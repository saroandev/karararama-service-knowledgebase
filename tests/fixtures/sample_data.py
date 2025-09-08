"""
Sample test data and fixtures
"""
import json
from pathlib import Path


# Sample PDF content for testing
SAMPLE_PDF_CONTENT = {
    "metadata": {
        "title": "Sample RAG Document", 
        "author": "Test Author",
        "file_size": 2048,
        "page_count": 3
    },
    "pages": [
        {
            "page_number": 1,
            "text": """Introduction to Retrieval-Augmented Generation

Retrieval-Augmented Generation (RAG) is a powerful technique that combines the capabilities of large language models with external knowledge retrieval. This approach allows AI systems to access up-to-date information and provide more accurate, contextual responses.

The RAG pipeline consists of several key components:
1. Document ingestion and preprocessing
2. Text chunking and embedding generation  
3. Vector storage and indexing
4. Query processing and retrieval
5. Response generation with source citations

This document provides a comprehensive overview of implementing a production-ready RAG system using modern technologies like Milvus, MinIO, and OpenAI.""",
            "metadata": {"page_number": 1, "section": "introduction"}
        },
        {
            "page_number": 2,
            "text": """Technical Architecture

The RAG system architecture includes the following components:

Vector Database: Milvus is used for storing and searching high-dimensional embeddings. It provides efficient similarity search capabilities with support for various distance metrics including cosine similarity and L2 distance.

Object Storage: MinIO serves as the object storage solution for raw documents and processed chunks. It offers S3-compatible API and can be deployed on-premises or in the cloud.

Embedding Models: The system supports multiple embedding models including OpenAI's text-embedding-3-small and open-source alternatives like sentence-transformers models.

Language Models: For response generation, the system integrates with OpenAI's GPT models and can also work with local models through Ollama.

API Layer: FastAPI provides a robust REST API with automatic documentation, request validation, and WebSocket support for real-time interactions.""",
            "metadata": {"page_number": 2, "section": "architecture"}
        },
        {
            "page_number": 3,
            "text": """Implementation Details

The implementation follows best practices for production deployment:

Data Processing Pipeline:
- PDF parsing using PyMuPDF for reliable text extraction
- Intelligent chunking strategies that respect sentence boundaries
- Batch processing for efficient embedding generation
- Error handling and retry mechanisms

Performance Optimizations:
- Connection pooling for database connections
- Caching mechanisms for frequently accessed data
- Asynchronous processing for I/O operations
- Monitoring and logging for production observability

Security Considerations:
- API key management through environment variables
- Input validation and sanitization
- Rate limiting and access controls
- Secure communication protocols

The system has been tested with various document types and can handle concurrent users while maintaining response times under 2 seconds for most queries.""",
            "metadata": {"page_number": 3, "section": "implementation"}
        }
    ]
}


# Sample document chunks for testing
SAMPLE_CHUNKS = [
    {
        "chunk_id": "sample_doc_001_chunk_001",
        "document_id": "sample_doc_001",
        "text": "Retrieval-Augmented Generation (RAG) is a powerful technique that combines the capabilities of large language models with external knowledge retrieval.",
        "metadata": {"page_number": 1, "section": "introduction", "chunk_index": 0},
        "token_count": 24,
        "char_count": 148
    },
    {
        "chunk_id": "sample_doc_001_chunk_002", 
        "document_id": "sample_doc_001",
        "text": "The RAG pipeline consists of several key components: document ingestion, text chunking, embedding generation, vector storage, query processing, and response generation.",
        "metadata": {"page_number": 1, "section": "introduction", "chunk_index": 1},
        "token_count": 26,
        "char_count": 161
    },
    {
        "chunk_id": "sample_doc_001_chunk_003",
        "document_id": "sample_doc_001", 
        "text": "Milvus is used for storing and searching high-dimensional embeddings. It provides efficient similarity search capabilities with support for various distance metrics.",
        "metadata": {"page_number": 2, "section": "architecture", "chunk_index": 2},
        "token_count": 25,
        "char_count": 158
    },
    {
        "chunk_id": "sample_doc_001_chunk_004",
        "document_id": "sample_doc_001",
        "text": "MinIO serves as the object storage solution for raw documents and processed chunks. It offers S3-compatible API and can be deployed on-premises or in the cloud.",
        "metadata": {"page_number": 2, "section": "architecture", "chunk_index": 3},
        "token_count": 28,
        "char_count": 156
    },
    {
        "chunk_id": "sample_doc_001_chunk_005",
        "document_id": "sample_doc_001",
        "text": "The system supports multiple embedding models including OpenAI's text-embedding-3-small and open-source alternatives like sentence-transformers models.",
        "metadata": {"page_number": 2, "section": "architecture", "chunk_index": 4},
        "token_count": 22,
        "char_count": 149
    }
]


# Sample queries for testing
SAMPLE_QUERIES = [
    {
        "question": "What is RAG and how does it work?",
        "expected_topics": ["retrieval", "augmented", "generation", "language models"],
        "difficulty": "basic"
    },
    {
        "question": "What vector database is used in the system?",
        "expected_topics": ["milvus", "vector", "database", "embeddings"],
        "difficulty": "specific"
    },
    {
        "question": "How does the system handle object storage?",
        "expected_topics": ["minio", "storage", "s3", "documents"],
        "difficulty": "specific"
    },
    {
        "question": "What are the key components of the RAG pipeline?", 
        "expected_topics": ["ingestion", "chunking", "embedding", "retrieval"],
        "difficulty": "comprehensive"
    },
    {
        "question": "What performance optimizations are implemented?",
        "expected_topics": ["caching", "connection pooling", "async", "monitoring"],
        "difficulty": "advanced"
    }
]


# Sample API responses for testing
SAMPLE_API_RESPONSES = {
    "health_check": {
        "status": "healthy",
        "timestamp": "2024-01-01T12:00:00Z",
        "services": {
            "milvus": "connected",
            "minio": "connected", 
            "embedding": "loaded"
        },
        "version": "1.0.0"
    },
    "successful_ingestion": {
        "success": True,
        "document_id": "sample_doc_001",
        "filename": "sample_document.pdf",
        "chunks_created": 5,
        "vectors_indexed": 5,
        "processing_time": 2.34,
        "metadata": {
            "title": "Sample RAG Document",
            "pages": 3,
            "file_size": 2048
        }
    },
    "successful_query": {
        "success": True,
        "question": "What is RAG?",
        "answer": "RAG (Retrieval-Augmented Generation) is a technique that combines language models with external knowledge retrieval to provide more accurate and contextual responses.",
        "sources": [
            {
                "chunk_id": "sample_doc_001_chunk_001",
                "text": "Retrieval-Augmented Generation (RAG) is a powerful technique...",
                "score": 0.95,
                "metadata": {"page_number": 1, "section": "introduction"}
            }
        ],
        "processing_time": 1.23
    },
    "error_responses": {
        "file_not_found": {
            "success": False,
            "error": "File not found",
            "error_code": "FILE_NOT_FOUND",
            "timestamp": "2024-01-01T12:00:00Z"
        },
        "processing_error": {
            "success": False,
            "error": "Document processing failed",
            "error_code": "PROCESSING_ERROR",
            "details": "PDF parsing error: corrupted file",
            "timestamp": "2024-01-01T12:00:00Z"
        },
        "query_error": {
            "success": False,
            "error": "No documents found in database",
            "error_code": "NO_DOCUMENTS",
            "timestamp": "2024-01-01T12:00:00Z"
        }
    }
}


def save_sample_data():
    """Save sample data to files for testing"""
    fixtures_dir = Path(__file__).parent
    
    # Save PDF content
    with open(fixtures_dir / "sample_pdf.json", "w") as f:
        json.dump(SAMPLE_PDF_CONTENT, f, indent=2)
    
    # Save chunks
    with open(fixtures_dir / "sample_chunks.json", "w") as f:
        json.dump(SAMPLE_CHUNKS, f, indent=2)
    
    # Save queries
    with open(fixtures_dir / "sample_queries.json", "w") as f:
        json.dump(SAMPLE_QUERIES, f, indent=2)
    
    # Save API responses
    with open(fixtures_dir / "sample_responses.json", "w") as f:
        json.dump(SAMPLE_API_RESPONSES, f, indent=2)


def load_sample_data(filename: str):
    """Load sample data from file"""
    fixtures_dir = Path(__file__).parent
    filepath = fixtures_dir / filename
    
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return None


if __name__ == "__main__":
    save_sample_data()
    print("Sample data saved to fixtures directory")