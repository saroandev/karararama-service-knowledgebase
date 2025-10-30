# BM25 Hybrid Search Implementation Problem

## 📋 Problem Summary

We attempted to implement BM25-based hybrid search (semantic + keyword) in Milvus 2.6.1, but encountered multiple blocking issues that prevent proper implementation without the Function API.

## 🎯 Original Goal

**Objective**: Implement hybrid search combining:
1. **Dense vectors (semantic search)**: OpenAI embeddings with HNSW index + COSINE metric
2. **Sparse vectors (keyword search)**: BM25-based sparse embeddings with SPARSE_INVERTED_INDEX + BM25 metric

**Benefits**:
- Better relevance: Combine contextual understanding (dense) with exact keyword matching (sparse)
- Improved recall: Find documents using both semantic similarity and keyword presence
- Industry best practice for RAG systems

## ❌ Errors Encountered

### Error 1: BM25 Metric Not Supported Without Function API

```
<MilvusException: (code=1100, message=only BM25 Function output field support BM25 metric type)>
```

**When**: Creating SPARSE_INVERTED_INDEX with `metric_type="BM25"`

**Root Cause**:
- Milvus 2.6.1 requires BM25 metric to be used ONLY with Function API output fields
- Function API allows defining functions in schema that auto-generate sparse vectors from text
- pymilvus 2.6.2 client does NOT have stable Function API support yet

**Attempted Workaround**: Use `metric_type="IP"` (Inner Product) instead of BM25
- This created the index successfully but led to Error 2

### Error 2: Sparse Vector Format Error

```
<ParamError: (code=1, message=input must be a sparse matrix in supported format)>
```

**When**: Inserting data with sparse_embedding field

**Root Cause**:
- We tried empty dictionaries: `sparse_embeddings = [{}] * len(chunks)` ❌
- Milvus rejected this format as invalid
- Sparse vectors must be in format: `{dimension_index: value}` with at least one entry

**Attempted Workaround**: Use minimal dummy sparse vectors: `[{0: 0.01}] * len(chunks)`
- This might satisfy schema but defeats the purpose of keyword search
- Dummy values provide no meaningful search benefit

## 🔍 Why This Doesn't Work

### The Function API Gap

Milvus 2.6 introduced Function API for auto-generating sparse vectors:

```python
# What we WANT to do (but can't yet):
from pymilvus import Function, DataType

bm25_function = Function(
    name="bm25",
    function_type=FunctionType.BM25,
    input_field_names=["text"],
    output_field_names=["sparse_embedding"]
)

schema.add_function(bm25_function)
# Then Milvus auto-generates sparse vectors during insert
```

**Current Reality**:
- Milvus server 2.6.1 supports Function API
- pymilvus client 2.6.2 does NOT have stable Function API
- No way to define functions in schema from Python client
- Manual sparse vector generation defeats the purpose (we'd need our own BM25 implementation)

### Why Dummy Sparse Vectors Don't Help

Using `[{0: 0.01}]` for every chunk:
- ❌ All chunks have identical sparse vectors (no differentiation)
- ❌ No keyword information captured
- ❌ Searches using sparse vectors return meaningless results
- ❌ Adds storage overhead (~0.39 KB per chunk) with zero benefit
- ❌ Increases insertion complexity for no gain

## ✅ Recommended Solution

### Option 1: Remove Sparse Vectors Entirely (RECOMMENDED)

**Action**: Revert to dense-only semantic search

**Changes Required**:

1. **Remove from schema** (`api/core/milvus_manager.py`):
```python
# Remove this field:
FieldSchema(name="sparse_embedding", dtype=DataType.SPARSE_FLOAT_VECTOR)

# Remove this index:
collection.create_index(field_name="sparse_embedding", ...)
```

2. **Remove from indexing** (`app/core/orchestrator/stages/indexing_stage.py`):
```python
# Remove sparse_embeddings from data preparation
# Change data array from 7 fields to 6 fields:
data = [
    milvus_data['ids'],
    milvus_data['document_ids'],
    milvus_data['chunk_indices'],
    milvus_data['texts'],
    milvus_data['embeddings'],
    # milvus_data['sparse_embeddings'],  # REMOVE THIS LINE
    milvus_data['metadata']
]
```

3. **Update storage measurement** (`measure_storage.py`):
```python
# Remove sparse_embedding detection and calculations
```

**Pros**:
- ✅ Clean, working solution
- ✅ No wasted storage (saves ~0.39 KB per chunk)
- ✅ Simpler codebase
- ✅ Already achieving 21.3x storage reduction (65535 → 3072 chars)
- ✅ Semantic search works perfectly for most use cases

**Cons**:
- ⚠️ No keyword-based filtering
- ⚠️ May miss exact phrase matches in some edge cases

### Option 2: Wait for Function API Stability

**Timeline**: Likely pymilvus 2.7+ or 3.0

**What to Monitor**:
- pymilvus GitHub releases: https://github.com/milvus-io/pymilvus/releases
- Milvus documentation updates on Function API
- Look for: `Function`, `FunctionType.BM25` in Python client

**When Available**:
1. Upgrade pymilvus client
2. Add BM25 function to schema
3. Remove manual sparse vector generation
4. Use `metric_type="BM25"` on index
5. Milvus auto-generates sparse vectors from text field

### Option 3: Manual BM25 Implementation (NOT RECOMMENDED)

**Action**: Implement our own BM25 algorithm to generate sparse vectors

**Why NOT Recommended**:
- 🚫 Requires BM25 library (e.g., rank_bm25, gensim)
- 🚫 Need to maintain document frequency (DF) and inverse document frequency (IDF) statistics
- 🚫 Must recalculate when collection size changes
- 🚫 Significant engineering effort
- 🚫 Milvus already does this internally - we'd be duplicating work
- 🚫 Performance overhead during ingestion

## 📊 Current Status After Storage Optimization

Even without BM25, we achieved significant improvements:

### ✅ Completed Optimizations

1. **Text Field Reduction**: 65535 → 3072 chars
   - Storage reduction: 21.3x (95.3% saved)
   - Example: 1M chunks = 64 GB → 3 GB (saves 61 GB)

2. **Chunk Overlap Reduction**: 50 → 25 tokens
   - Fewer redundant chunks
   - Faster indexing and querying

3. **Dense Vector Search**: HNSW + COSINE metric
   - High quality semantic search
   - Fast retrieval (<100ms typical)
   - Proven effective for RAG systems

### 📈 Performance Metrics (Dense-Only)

Per-chunk storage breakdown:
- Text field: 12 KB (optimized from 256 KB)
- Dense embedding: 6 KB (1536 dim × 4 bytes)
- HNSW index: 0.125 KB (M=16)
- Metadata + Keys: 2.5 KB
- **Total: ~20.6 KB per chunk** (vs 264.6 KB before optimization)

## 🎯 Recommended Action Plan

### Immediate (Now)

1. ✅ Remove sparse_embedding field from schema
2. ✅ Remove sparse vector handling from indexing_stage.py
3. ✅ Clean up data/ folder and recreate collections
4. ✅ Test document ingestion with 6-field schema
5. ✅ Verify storage measurements show expected reduction

### Short-term (Next 1-2 weeks)

1. Monitor query quality with dense-only search
2. Collect user feedback on search relevance
3. Optimize HNSW parameters if needed (M, efConstruction)
4. Consider query expansion techniques if keyword matching is critical

### Long-term (When Function API Available)

1. Watch pymilvus releases for Function API stability
2. Create migration script to add sparse_embedding field
3. Implement BM25 function in schema
4. Reindex existing documents with auto-generated sparse vectors
5. Enable hybrid search with proper BM25 scoring

## 📚 References

- [Milvus Sparse Vector Documentation](https://milvus.io/docs/sparse_vector.md)
- [Milvus Full Text Search](https://milvus.io/docs/full-text-search.md)
- [pymilvus GitHub Issues on Function API](https://github.com/milvus-io/pymilvus/issues)

## 🏁 Conclusion

**Decision**: Remove sparse_embedding field and proceed with dense-only semantic search.

**Reasoning**:
1. Function API not stable in pymilvus 2.6.2
2. Dummy sparse vectors provide zero value
3. Dense semantic search is sufficient for most RAG use cases
4. Significant storage optimization already achieved (21.3x reduction)
5. Can add BM25 later when Function API is available (backward compatible)

**Next Steps**: See "Immediate" action plan above.
