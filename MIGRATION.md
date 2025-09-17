# Migration Guide: From Legacy to Modular Architecture

This guide helps you migrate from the old monolithic structure to the new modular architecture.

## 📋 Overview

The RAG system has been refactored from monolithic files to a clean, modular architecture with clear separation of concerns.

## 🔄 Import Changes

### Old Structure → New Structure

#### Embeddings
```python
# OLD
from app.embed import generate_embedding, generate_embeddings_batch

# NEW
from app.core.embeddings import default_embedding_generator
# or
from app.core.embeddings import create_embedding_generator
```

#### Generation (LLM)
```python
# OLD
from app.generate import generate_answer

# NEW
from app.core.generation import default_generator
# or
from app.core.generation import create_answer_generator
```

#### Parsing
```python
# OLD
from app.parse import parse_pdf

# NEW
from app.core.parsing import default_parser
# or
from app.core.parsing import create_pdf_parser
```

#### Indexing
```python
# OLD
from app.index import MilvusIndexer, insert_chunks

# NEW
from app.core.indexing import default_indexer
# or
from app.core.indexing import create_milvus_indexer
```

#### Retrieval
```python
# OLD
from app.retrieve import retrieve_relevant_chunks

# NEW
from app.core.retrieval import default_retriever
# or
from app.core.retrieval import create_retriever
```

#### Storage
```python
# OLD
from app.storage import MinioStorage, DocumentStorage

# NEW
from app.core.storage import storage
# Storage is now a singleton with all methods
```

#### Chunking
```python
# OLD
from app.chunk import chunk_text, chunk_by_tokens

# NEW
from app.core.chunking import get_default_chunker
# or specific chunkers
from app.core.chunking import TextChunker, SemanticChunker, HybridChunker
```

#### Ingestion
```python
# OLD
from app.ingest import IngestionPipeline, ingestion_pipeline

# NEW
from app.pipelines import IngestPipeline
```

## 🛠️ Code Examples

### Example 1: Document Ingestion

**Old Way:**
```python
from app.ingest import ingestion_pipeline

result = ingestion_pipeline.ingest_document_sync(
    file_obj=file,
    filename="document.pdf",
    metadata={"source": "upload"}
)
```

**New Way:**
```python
from app.pipelines import IngestPipeline
import asyncio

pipeline = IngestPipeline()
result = asyncio.run(pipeline.run(
    file_obj=file,
    filename="document.pdf",
    metadata={"source": "upload"}
))
```

### Example 2: Query Processing

**Old Way:**
```python
from app.retrieve import retrieve_relevant_chunks
from app.generate import generate_answer

chunks = retrieve_relevant_chunks(query, top_k=5)
answer = generate_answer(query, chunks)
```

**New Way:**
```python
from app.pipelines import QueryPipeline
import asyncio

pipeline = QueryPipeline()
result = asyncio.run(pipeline.run(
    question=query,
    top_k=5
))
answer = result.data["answer"]
```

### Example 3: Custom Embeddings

**Old Way:**
```python
from app.embed import generate_embedding

embedding = generate_embedding("text to embed")
```

**New Way:**
```python
from app.core.embeddings import default_embedding_generator

embedding = default_embedding_generator.generate_embedding("text to embed")
```

## 📁 New Directory Structure

```
app/
├── core/                  # Core business logic
│   ├── embeddings/        # Embedding generation
│   ├── generation/        # LLM answer generation
│   ├── parsing/           # Document parsing
│   ├── indexing/          # Vector database indexing
│   ├── retrieval/         # Document retrieval
│   ├── chunking/          # Text chunking strategies
│   └── storage/           # MinIO storage operations
│
├── pipelines/             # Orchestration pipelines
│   ├── ingest_pipeline.py
│   └── query_pipeline.py
│
├── utils/                 # Utility functions
│   ├── logging.py
│   ├── decorators.py
│   ├── validators.py
│   └── helpers.py
│
└── legacy/                # Old files (to be removed)
```

## ✅ Benefits of New Architecture

1. **Modularity**: Each component has a single responsibility
2. **Testability**: Easier to test individual components
3. **Maintainability**: Clear structure makes maintenance easier
4. **Extensibility**: Easy to add new features or swap implementations
5. **Reusability**: Components can be reused across different pipelines

## 🚀 Quick Start

For most use cases, you can use the high-level pipeline interfaces:

```python
from app.pipelines import IngestPipeline, QueryPipeline
import asyncio

# Ingest documents
ingest = IngestPipeline()
await ingest.run(file_obj=file, filename="doc.pdf")

# Query documents
query = QueryPipeline()
result = await query.run(question="What is RAG?")
```

## ⚠️ Breaking Changes

1. All main functions are now async (use `asyncio.run()` or `await`)
2. Storage is now a singleton (access via `storage` object)
3. Chunking strategies are now classes instead of functions
4. Pipeline results are wrapped in `PipelineResult` objects

## 📝 Notes

- The old files are kept in `app/legacy/` for reference
- Backward compatibility wrappers exist in some modules
- Configuration is centralized in `app/config.py`
- All utilities are now in `app/utils/`

## 🔗 Related Documents

- [REFACTORING.md](REFACTORING.md) - Detailed refactoring plan
- [README.md](README.md) - Project overview
- [CLAUDE.md](CLAUDE.md) - Development guide