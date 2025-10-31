# 🔍 Search Methods Implementation Guide

## Overview

This document explains how to implement **3 different search methods** (Hybrid, Semantic, BM25) in your RAG service, allowing users to choose their preferred search strategy per query.

---

## 📋 Table of Contents

1. [What Are The Search Methods?](#what-are-the-search-methods)
2. [Why Multiple Search Methods?](#why-multiple-search-methods)
3. [Architecture Overview](#architecture-overview)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Testing Guide](#testing-guide)
6. [Frontend Integration](#frontend-integration)
7. [Performance Considerations](#performance-considerations)

---

## What Are The Search Methods?

### 1️⃣ **Hybrid Search** (Default - Most Powerful)
- **How it works**: Combines Semantic (dense vector) + BM25 (sparse vector) searches, then fuses results using RRF (Reciprocal Rank Fusion)
- **Best for**: General queries, comprehensive results
- **Pros**: Leverages strengths of both methods, highest recall
- **Cons**: Slower (runs both searches), more complex
- **Score Range**: 0-100 (normalized RRF score)

**Example Use Case**: "What are contract termination conditions?" → Finds both semantically related content AND documents with exact keywords.

### 2️⃣ **Semantic Search** (Meaning-Based)
- **How it works**: Only uses dense vector embeddings (1536-dim) with COSINE similarity
- **Best for**: Conceptual queries, finding related content even without exact keywords
- **Pros**: Finds synonyms and related concepts, understands context
- **Cons**: May miss exact keyword matches
- **Score Range**: 0-100 (COSINE similarity × 100)

**Example Use Case**: "contract termination" → Also finds "contract cancellation", "agreement ending", "akdin sona ermesi"

### 3️⃣ **BM25 Search** (Keyword-Based)
- **How it works**: Only uses sparse vectors with BM25 keyword matching algorithm
- **Best for**: Exact term searches, specific article/clause numbers
- **Pros**: Fast, precise for exact matches, works like traditional search
- **Cons**: Doesn't understand synonyms or context
- **Score Range**: 0-100 (normalized BM25 score)

**Example Use Case**: "Madde 18" → Finds documents containing exactly "Madde 18"

---

## Why Multiple Search Methods?

### Problem Statement
Different queries require different search strategies:

| Query Type | Best Method | Why |
|------------|-------------|-----|
| "Contract cancellation process?" | **Hybrid** | Needs both understanding + exact terms |
| "What is force majeure?" | **Semantic** | Conceptual, may have various phrasings |
| "Article 18 paragraph 3" | **BM25** | Exact term match required |
| "Legal obligations in lease agreements" | **Hybrid** | Complex, benefits from both approaches |

### Benefits of This Implementation

✅ **Flexibility**: Users can choose the best strategy per query
✅ **Debugging**: Easily compare which method works best
✅ **Performance**: Use BM25-only for faster exact searches
✅ **Accuracy**: Use Semantic-only when context matters more than keywords
✅ **Backward Compatible**: Default is Hybrid, existing code unaffected

---

## Architecture Overview

### High-Level Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client Request                            │
│  {                                                                │
│    "question": "Contract termination",                           │
│    "search_mode": "semantic"  ← User chooses method             │
│  }                                                                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   API Endpoint Layer                              │
│  • Validates search_mode enum                                    │
│  • Passes to query logic                                         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                  Conditional Search Logic                         │
│                                                                   │
│  if search_mode == "semantic":                                   │
│      ┌────────────────────────────────┐                         │
│      │  Dense Vector Search Only      │                         │
│      │  • Field: embedding            │                         │
│      │  • Metric: COSINE              │                         │
│      │  • Score: similarity × 100     │                         │
│      └────────────────────────────────┘                         │
│                                                                   │
│  elif search_mode == "bm25":                                     │
│      ┌────────────────────────────────┐                         │
│      │  BM25 Search Only              │                         │
│      │  • Field: sparse               │                         │
│      │  • Metric: BM25                │                         │
│      │  • Score: (score/max) × 100    │                         │
│      └────────────────────────────────┘                         │
│                                                                   │
│  else:  # hybrid (default)                                       │
│      ┌────────────────────────────────┐                         │
│      │  Both Searches + RRF Fusion    │                         │
│      │  • Dense: embedding (COSINE)   │                         │
│      │  • Sparse: sparse (BM25)       │                         │
│      │  • Fusion: RRF (k=60)          │                         │
│      │  • Score: (rrf/max_rrf) × 100  │                         │
│      └────────────────────────────────┘                         │
│                                                                   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Return Results (0-100)                         │
│  [                                                                │
│    {"score": 95.3, "text": "...", "document_title": "..."},     │
│    {"score": 87.6, "text": "...", "document_title": "..."}      │
│  ]                                                                │
└──────────────────────────────────────────────────────────────────┘
```

### Component Interaction

```
┌─────────────────┐
│  schemas/api/   │  1. Define SearchMode enum
│  requests/      │     and add to request schemas
│  collection.py  │
│  query.py       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  api/endpoints/ │  2. Use search_mode in
│  collections_   │     conditional logic
│  query.py       │
│  query.py       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  app/core/      │  3. Pass search_mode
│  orchestrator/  │     through handler chain
│  handlers/      │
└─────────────────┘
```

---

## Step-by-Step Implementation

### Step 1: Define SearchMode Enum

**File**: `schemas/api/requests/collection.py` (or `query.py`)

```python
from enum import Enum
from pydantic import BaseModel, Field

class SearchMode(str, Enum):
    """Search mode options for collection queries"""
    HYBRID = "hybrid"      # Semantic + BM25 with RRF fusion (default)
    SEMANTIC = "semantic"  # Dense vector only
    BM25 = "bm25"         # Sparse vector (keyword) only
```

**Key Points**:
- Inherits from `str` and `Enum` for FastAPI compatibility
- Use lowercase values for consistency
- Add descriptive comments

---

### Step 2: Add search_mode to Request Schemas

#### For Collections Endpoint

**File**: `schemas/api/requests/collection.py`

```python
class CollectionQueryRequest(BaseModel):
    """Request schema for querying collections"""
    question: str = Field(..., description="Question to search for")
    collections: List[CollectionFilter] = Field(...)
    top_k: int = Field(default=5, ge=1, le=20)

    # Add search_mode field
    search_mode: SearchMode = Field(
        default=SearchMode.HYBRID,
        description="Search mode: 'hybrid', 'semantic', or 'bm25'"
    )

    # ... other fields ...
```

#### For Chat Endpoint

**File**: `schemas/api/requests/query.py`

```python
class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    question: str = Field(...)
    conversation_id: str = Field(...)
    sources: List[str] = Field(default=[])
    collections: Optional[List[CollectionFilter]] = Field(default=None)
    top_k: int = Field(default=5)

    # Add search_mode field
    search_mode: SearchMode = Field(
        default=SearchMode.HYBRID,
        description="Search mode for collections: 'hybrid', 'semantic', or 'bm25'"
    )

    # ... other fields ...
```

**Important**:
- Default should be `SearchMode.HYBRID` for backward compatibility
- Add to examples in `model_config`:

```python
model_config = {
    "json_schema_extra": {
        "examples": [
            {
                "question": "Contract termination?",
                "collections": [...],
                "search_mode": "hybrid"  # ← Add this
            }
        ]
    }
}
```

---

### Step 3: Implement Conditional Search Logic

**File**: `api/endpoints/collections_query.py`

```python
from schemas.api.requests.collection import CollectionQueryRequest, SearchMode

@router.post("/collections/query")
async def query_collections(
    request: CollectionQueryRequest,
    user: UserContext = Depends(get_current_user)
):
    # ... setup code ...

    client = milvus_client_manager.get_client()

    # Log selected mode
    mode_name = {
        SearchMode.HYBRID: "Hybrid Search (Semantic + BM25)",
        SearchMode.SEMANTIC: "Semantic Search Only (Dense Vector)",
        SearchMode.BM25: "BM25 Search Only (Keyword)"
    }.get(request.search_mode, "Hybrid Search")

    logger.info(f"🔍 SEARCH MODE: {mode_name}")

    # Conditional search logic
    for collection_info in collections_to_search:
        try:
            if request.search_mode == SearchMode.SEMANTIC:
                # ===== SEMANTIC ONLY =====
                results = await search_semantic_only(
                    client=client,
                    collection_name=collection_info["collection_name"],
                    query_embedding=query_embedding,
                    top_k=request.top_k
                )

            elif request.search_mode == SearchMode.BM25:
                # ===== BM25 ONLY =====
                results = await search_bm25_only(
                    client=client,
                    collection_name=collection_info["collection_name"],
                    question=request.question,
                    top_k=request.top_k
                )

            else:  # SearchMode.HYBRID (default)
                # ===== HYBRID (BOTH + RRF) =====
                results = await search_hybrid(
                    client=client,
                    collection_name=collection_info["collection_name"],
                    query_embedding=query_embedding,
                    question=request.question,
                    top_k=request.top_k
                )

            # Process results...

        except Exception as e:
            logger.error(f"Search failed: {e}")
            continue
```

---

### Step 4: Implement Each Search Method

#### 4.1 Semantic Only Search

```python
async def search_semantic_only(client, collection_name, query_embedding, top_k):
    """Execute semantic-only search"""

    # 1. Search with dense vector
    logger.info("🧠 Semantic search (dense vector only)...")
    results = client.search(
        collection_name=collection_name,
        data=[query_embedding],  # 1536-dim embedding
        anns_field='embedding',  # Dense vector field
        limit=top_k,
        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
    )

    # 2. Process results
    search_results = []
    for rank, result in enumerate(results[0], 1):
        entity = result.get('entity', {})
        distance = result.get('distance', 0)

        # COSINE similarity: convert distance to similarity
        similarity = 1 - distance

        # Normalize to 0-100
        final_score = similarity * 100

        logger.info(f"   {rank}. Score: {final_score:.1f}/100 | {entity.get('document_id')}")

        search_results.append({
            'score': final_score,
            'document_id': entity.get('document_id'),
            'text': entity.get('text'),
            'metadata': entity.get('metadata'),
            # ... other fields ...
        })

    return search_results
```

**Key Points**:
- Only searches `embedding` field (dense vector)
- Distance is COSINE distance (0 = same, 1 = opposite)
- Convert to similarity: `similarity = 1 - distance`
- Normalize to 0-100: `score = similarity × 100`

---

#### 4.2 BM25 Only Search

```python
async def search_bm25_only(client, collection_name, question, top_k):
    """Execute BM25-only search"""

    # 1. Search with sparse vector (BM25)
    logger.info("🔤 BM25 search (keyword only)...")
    results = client.search(
        collection_name=collection_name,
        data=[question],         # Raw text query (not embedding!)
        anns_field='sparse',     # Sparse vector field
        limit=top_k,
        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
    )

    # 2. Find max score for normalization
    max_bm25 = max([r.get('distance', 0) for r in results[0]], default=1.0)
    if max_bm25 == 0:
        max_bm25 = 1.0

    # 3. Process results
    search_results = []
    for rank, result in enumerate(results[0], 1):
        entity = result.get('entity', {})
        bm25_score = result.get('distance', 0)  # BM25 score (higher = better)

        # Normalize to 0-100
        final_score = (bm25_score / max_bm25) * 100

        logger.info(f"   {rank}. Score: {final_score:.1f}/100 | {entity.get('document_id')}")

        search_results.append({
            'score': final_score,
            'document_id': entity.get('document_id'),
            'text': entity.get('text'),
            'metadata': entity.get('metadata'),
            # ... other fields ...
        })

    return search_results
```

**Key Points**:
- Searches `sparse` field (BM25 vector)
- Pass **text query directly** (not embedding!)
- BM25 score is in `distance` field (higher = better match)
- Normalize by dividing by max score in batch
- Score range: 0-100

---

#### 4.3 Hybrid Search (Semantic + BM25 + RRF)

```python
async def search_hybrid(client, collection_name, query_embedding, question, top_k):
    """Execute hybrid search with RRF fusion"""

    # 1. Dense vector search (Semantic)
    logger.info("🧠 Dense search (semantic)...")
    dense_results = client.search(
        collection_name=collection_name,
        data=[query_embedding],
        anns_field='embedding',
        limit=top_k * 2,  # Fetch more for fusion
        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
    )

    # 2. BM25 search (Keyword)
    logger.info("🔤 BM25 search (keyword)...")
    bm25_results = client.search(
        collection_name=collection_name,
        data=[question],
        anns_field='sparse',
        limit=top_k * 2,  # Fetch more for fusion
        output_fields=['document_id', 'chunk_index', 'text', 'metadata']
    )

    # 3. Build score dictionaries
    logger.info("🔀 Fusing results with RRF...")

    semantic_scores = {}
    for rank, result in enumerate(dense_results[0], 1):
        entity = result.get('entity', {})
        doc_id = entity.get('document_id')
        chunk_idx = entity.get('chunk_index', 0)
        distance = result.get('distance', 0)
        similarity = 1 - distance  # COSINE similarity

        key = (doc_id, chunk_idx)
        semantic_scores[key] = {
            'score': similarity,
            'rank': rank,
            'result': result
        }

    bm25_scores = {}
    for rank, result in enumerate(bm25_results[0], 1):
        entity = result.get('entity', {})
        doc_id = entity.get('document_id')
        chunk_idx = entity.get('chunk_index', 0)
        bm25_score = result.get('distance', 0)

        key = (doc_id, chunk_idx)
        bm25_scores[key] = {
            'score': bm25_score,
            'rank': rank,
            'result': result
        }

    # 4. Calculate RRF scores
    k = 60  # RRF constant
    all_doc_keys = set(semantic_scores.keys()) | set(bm25_scores.keys())
    rrf_results = []

    for doc_key in all_doc_keys:
        sem_data = semantic_scores.get(doc_key, {'score': 0, 'rank': 9999, 'result': None})
        bm25_data = bm25_scores.get(doc_key, {'score': 0, 'rank': 9999, 'result': None})

        # RRF formula: sum of 1/(k + rank_i)
        rrf_score = (1 / (k + sem_data['rank'])) + (1 / (k + bm25_data['rank']))

        base_result = sem_data['result'] or bm25_data['result']
        if base_result is None:
            continue

        rrf_results.append({
            'doc_key': doc_key,
            'semantic_score': sem_data['score'],
            'semantic_rank': sem_data['rank'],
            'bm25_score': bm25_data['score'],
            'bm25_rank': bm25_data['rank'],
            'rrf_score': rrf_score,
            'result': base_result
        })

    # 5. Sort by RRF and normalize to 0-100
    rrf_results.sort(key=lambda x: x['rrf_score'], reverse=True)
    rrf_results = rrf_results[:top_k]

    max_rrf = (1 / (k + 1)) + (1 / (k + 1))  # Both rank 1

    search_results = []
    for idx, rrf_item in enumerate(rrf_results, 1):
        rrf_score = rrf_item['rrf_score']

        # Normalize to 0-100
        final_score = (rrf_score / max_rrf) * 100

        # Log which methods found it
        in_semantic = rrf_item['semantic_rank'] < 9999
        in_bm25 = rrf_item['bm25_rank'] < 9999

        if in_semantic and in_bm25:
            match_type = "📊 BOTH"
        elif in_semantic:
            match_type = "🧠 Semantic only"
        else:
            match_type = "🔤 BM25 only"

        logger.info(f"   {idx}. Score: {final_score:.1f}/100 | {match_type}")

        entity = rrf_item['result'].get('entity', {})
        search_results.append({
            'score': final_score,
            'document_id': entity.get('document_id'),
            'text': entity.get('text'),
            'metadata': entity.get('metadata'),
            # ... other fields ...
        })

    return search_results
```

**Key Points**:
- Runs **both** searches (dense + sparse)
- Fetches `top_k * 2` from each to have enough for fusion
- RRF formula: `1/(k + rank_semantic) + 1/(k + rank_bm25)`
- `k = 60` is standard RRF constant
- `max_rrf` assumes both methods rank document as #1
- Normalize final RRF score to 0-100
- Logs which method(s) found each document

---

### Step 5: Pass search_mode Through Handler Chain

If using orchestrator pattern:

**File**: `app/core/orchestrator/handlers/collection_handler.py`

```python
class CollectionServiceHandler(BaseHandler):
    # ... init code ...

    async def search(
        self,
        question: str,
        top_k: int = 5,
        min_relevance_score: float = 0.7,
        search_mode: str = "hybrid",  # ← Add this parameter
        **kwargs
    ) -> HandlerResult:
        """Search in collections via internal HTTP endpoint"""

        logger.info(f"📦 Querying collections: {[c.name for c in self.collections]}")
        logger.info(f"🔍 Search mode: {search_mode}")  # ← Log it

        # Prepare request payload
        request_payload = {
            "question": question,
            "collections": [...],
            "top_k": top_k,
            "min_relevance_score": min_relevance_score,
            "search_mode": search_mode  # ← Pass to collections/query endpoint
        }

        # Call internal endpoint
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8080/api/collections/query",
                json=request_payload,
                headers={"Authorization": f"Bearer {self.user_access_token}"}
            )

        # ... process response ...
```

**File**: `app/core/orchestrator/orchestrator.py`

```python
class QueryOrchestrator:
    async def execute_query(self, request: QueryRequest, user: UserContext, ...):
        # ... setup code ...

        # Execute handlers with search_mode
        handler_results = await asyncio.gather(
            *[
                handler.search(
                    question=request.question,
                    top_k=request.top_k,
                    min_relevance_score=request.min_relevance_score,
                    search_mode=request.search_mode.value  # ← Pass enum value
                )
                for handler in handlers
            ],
            return_exceptions=True
        )

        # ... aggregate results ...
```

---

## Testing Guide

### Unit Testing

**File**: `tests/unit/test_search_modes.py`

```python
import pytest
from schemas.api.requests.collection import SearchMode, CollectionQueryRequest

def test_search_mode_enum():
    """Test SearchMode enum values"""
    assert SearchMode.HYBRID.value == "hybrid"
    assert SearchMode.SEMANTIC.value == "semantic"
    assert SearchMode.BM25.value == "bm25"

def test_search_mode_default():
    """Test default search mode is hybrid"""
    request = CollectionQueryRequest(
        question="Test",
        collections=[{"name": "test", "scopes": ["private"]}]
    )
    assert request.search_mode == SearchMode.HYBRID

def test_search_mode_explicit():
    """Test explicit search mode setting"""
    request = CollectionQueryRequest(
        question="Test",
        collections=[{"name": "test", "scopes": ["private"]}],
        search_mode="semantic"
    )
    assert request.search_mode == SearchMode.SEMANTIC
```

---

### Integration Testing

```bash
# Test Hybrid Search (default)
curl -X POST "http://localhost:8080/api/collections/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -d '{
    "question": "Contract termination",
    "collections": [{"name": "contracts", "scopes": ["private"]}],
    "search_mode": "hybrid"
  }'

# Test Semantic Only
curl -X POST "http://localhost:8080/api/collections/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -d '{
    "question": "Contract termination",
    "collections": [{"name": "contracts", "scopes": ["private"]}],
    "search_mode": "semantic"
  }'

# Test BM25 Only
curl -X POST "http://localhost:8080/api/collections/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -d '{
    "question": "Article 18",
    "collections": [{"name": "laws", "scopes": ["private"]}],
    "search_mode": "bm25"
  }'
```

---

### A/B Testing Different Methods

```python
import httpx
import asyncio

async def compare_search_methods(question, collections):
    """Compare all three search methods"""

    modes = ["hybrid", "semantic", "bm25"]
    results = {}

    for mode in modes:
        payload = {
            "question": question,
            "collections": collections,
            "search_mode": mode,
            "top_k": 5
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8080/api/collections/query",
                json=payload,
                headers={"Authorization": f"Bearer {token}"}
            )

            data = response.json()
            results[mode] = {
                "processing_time": data["processing_time"],
                "total_results": data["total_results"],
                "top_score": data["results"][0]["score"] if data["results"] else 0
            }

    return results

# Example usage
results = await compare_search_methods(
    question="What are force majeure conditions?",
    collections=[{"name": "contracts", "scopes": ["private"]}]
)

print("Comparison:")
for mode, metrics in results.items():
    print(f"{mode:10s} | Time: {metrics['processing_time']:.3f}s | "
          f"Results: {metrics['total_results']} | Top Score: {metrics['top_score']:.1f}/100")

# Output:
# hybrid     | Time: 0.234s | Results: 5 | Top Score: 95.3/100
# semantic   | Time: 0.089s | Results: 5 | Top Score: 92.7/100
# bm25       | Time: 0.067s | Results: 4 | Top Score: 88.1/100
```

---

## Frontend Integration

### React Example

```jsx
import React, { useState } from 'react';

const SearchModeSelector = () => {
  const [searchMode, setSearchMode] = useState('hybrid');
  const [question, setQuestion] = useState('');
  const [results, setResults] = useState([]);

  const searchModes = [
    {
      value: 'hybrid',
      label: 'Hybrid (Best Results)',
      icon: '📊',
      description: 'Combines semantic understanding + exact keywords'
    },
    {
      value: 'semantic',
      label: 'Semantic (Meaning)',
      icon: '🧠',
      description: 'Finds conceptually related content'
    },
    {
      value: 'bm25',
      label: 'BM25 (Keywords)',
      icon: '🔤',
      description: 'Exact term matching'
    }
  ];

  const handleSearch = async () => {
    const response = await fetch('/api/collections/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        question,
        collections: [{ name: 'contracts', scopes: ['private'] }],
        search_mode: searchMode,
        top_k: 5
      })
    });

    const data = await response.json();
    setResults(data.results);
  };

  return (
    <div className="search-container">
      <div className="search-mode-selector">
        <label>Search Method:</label>
        {searchModes.map(mode => (
          <div
            key={mode.value}
            className={`mode-option ${searchMode === mode.value ? 'active' : ''}`}
            onClick={() => setSearchMode(mode.value)}
          >
            <span className="icon">{mode.icon}</span>
            <span className="label">{mode.label}</span>
            <span className="description">{mode.description}</span>
          </div>
        ))}
      </div>

      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Enter your question..."
      />

      <button onClick={handleSearch}>Search</button>

      <div className="results">
        {results.map((result, idx) => (
          <div key={idx} className="result-item">
            <div className="score">Score: {result.score.toFixed(1)}/100</div>
            <div className="title">{result.document_title}</div>
            <div className="text">{result.text}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SearchModeSelector;
```

---

### Vue.js Example

```vue
<template>
  <div class="search-container">
    <div class="search-mode-selector">
      <h3>Choose Search Method</h3>
      <div class="mode-buttons">
        <button
          v-for="mode in searchModes"
          :key="mode.value"
          :class="['mode-btn', { active: searchMode === mode.value }]"
          @click="searchMode = mode.value"
        >
          <span class="icon">{{ mode.icon }}</span>
          <span class="label">{{ mode.label }}</span>
          <small>{{ mode.description }}</small>
        </button>
      </div>
    </div>

    <input
      v-model="question"
      type="text"
      placeholder="Enter your question..."
      @keyup.enter="search"
    />

    <button @click="search">Search</button>

    <div v-if="results.length" class="results">
      <div v-for="(result, idx) in results" :key="idx" class="result-card">
        <div class="score-badge">{{ result.score.toFixed(1) }}/100</div>
        <h4>{{ result.document_title }}</h4>
        <p>{{ result.text }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const searchMode = ref('hybrid');
const question = ref('');
const results = ref([]);

const searchModes = [
  { value: 'hybrid', label: 'Hybrid', icon: '📊', description: 'Best overall' },
  { value: 'semantic', label: 'Semantic', icon: '🧠', description: 'Meaning-based' },
  { value: 'bm25', label: 'BM25', icon: '🔤', description: 'Keyword-based' }
];

const search = async () => {
  const response = await fetch('/api/collections/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token.value}`
    },
    body: JSON.stringify({
      question: question.value,
      collections: [{ name: 'contracts', scopes: ['private'] }],
      search_mode: searchMode.value,
      top_k: 5
    })
  });

  const data = await response.json();
  results.value = data.results;
};
</script>
```

---

## Performance Considerations

### Speed Comparison

| Method | Avg Time | Searches Run | Best For |
|--------|----------|--------------|----------|
| **BM25** | ~50-80ms | 1 (sparse only) | Speed-critical, exact matches |
| **Semantic** | ~80-120ms | 1 (dense only) | Balance of speed + accuracy |
| **Hybrid** | ~150-250ms | 2 (both + fusion) | Maximum accuracy |

### Optimization Tips

#### 1. **Use BM25 for Known Query Patterns**
```python
# Detect patterns that work better with BM25
def auto_select_mode(question: str) -> str:
    patterns = [
        r"madde\s+\d+",        # Article numbers
        r"fıkra\s+\d+",        # Paragraph numbers
        r"bent\s+[a-z]",       # Clauses
        r"\d{4}/\d+",          # Law numbers (e.g., 6098/123)
    ]

    for pattern in patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return "bm25"  # Exact match is better

    return "hybrid"  # Default to comprehensive search
```

#### 2. **Cache Embeddings**
```python
# For semantic/hybrid modes, cache embeddings
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_embedding(question: str) -> List[float]:
    return embedding_service.generate_embedding(question)

# Use cached version
if search_mode in ["semantic", "hybrid"]:
    query_embedding = get_cached_embedding(request.question)
```

#### 3. **Parallel Execution for Hybrid**
```python
# Run dense and BM25 searches truly in parallel
import asyncio

async def search_hybrid_parallel(client, collection, query_embedding, question, top_k):
    # Run both searches concurrently
    dense_task = asyncio.create_task(
        client.search(collection, data=[query_embedding], anns_field='embedding', ...)
    )

    bm25_task = asyncio.create_task(
        client.search(collection, data=[question], anns_field='sparse', ...)
    )

    # Wait for both
    dense_results, bm25_results = await asyncio.gather(dense_task, bm25_task)

    # Fuse results...
    return fused_results
```

#### 4. **Reduce top_k for Faster Responses**
```python
# For hybrid mode, reduce fetched results
if search_mode == "hybrid":
    # Only need top_k * 1.5 instead of * 2 for most cases
    search_limit = int(top_k * 1.5)
else:
    search_limit = top_k
```

---

## Common Pitfalls & Solutions

### ❌ Problem 1: Scores Not Comparable Across Methods

**Issue**: Each method produces different score ranges/meanings

**Solution**: Always normalize to 0-100
```python
# Semantic: similarity × 100
semantic_score = (1 - distance) * 100

# BM25: normalize by max in batch
bm25_score = (score / max_score) * 100

# Hybrid: normalize RRF
hybrid_score = (rrf_score / max_rrf) * 100
```

---

### ❌ Problem 2: BM25 Returns Empty for Misspellings

**Issue**: BM25 can't handle typos or synonyms

**Recommendation**: Use hybrid or semantic for user-facing search
```python
# Smart fallback
if search_mode == "bm25" and len(results) == 0:
    logger.warning("BM25 returned no results, falling back to semantic")
    search_mode = "semantic"
    results = search_semantic_only(...)
```

---

### ❌ Problem 3: Hybrid Too Slow for Real-Time

**Issue**: Running two searches + fusion takes too long

**Solutions**:
1. Cache embeddings (semantic part)
2. Use async parallel execution
3. Reduce `top_k * 2` to `top_k * 1.5`
4. Default to `semantic` for user-facing, save `hybrid` for batch jobs

```python
# Smart defaults based on context
def get_default_search_mode(context: str) -> str:
    if context == "real-time-chat":
        return "semantic"  # Faster, good enough
    elif context == "batch-analysis":
        return "hybrid"    # Accuracy matters more
    elif context == "autocomplete":
        return "bm25"      # Speed critical
    else:
        return "hybrid"
```

---

### ❌ Problem 4: Users Don't Know Which to Choose

**Issue**: Too technical for end users

**Solution**: Provide smart recommendations
```python
# UI Helper
def get_recommended_mode(query: str, use_case: str) -> dict:
    recommendations = {
        "legal-clause-search": {
            "mode": "bm25",
            "reason": "Exact article/clause numbers work best with keyword matching"
        },
        "conceptual-research": {
            "mode": "semantic",
            "reason": "Understanding meaning is more important than exact words"
        },
        "general-qa": {
            "mode": "hybrid",
            "reason": "Best balance of accuracy for varied questions"
        }
    }

    # Auto-detect based on query
    if re.search(r"\d+", query):  # Contains numbers
        return recommendations["legal-clause-search"]
    elif len(query.split()) > 10:  # Long query
        return recommendations["conceptual-research"]
    else:
        return recommendations["general-qa"]
```

---

## Monitoring & Analytics

### Log Key Metrics

```python
import time
from dataclasses import dataclass

@dataclass
class SearchMetrics:
    search_mode: str
    processing_time: float
    dense_time: float = 0.0
    bm25_time: float = 0.0
    fusion_time: float = 0.0
    results_count: int = 0
    top_score: float = 0.0

def log_search_metrics(metrics: SearchMetrics):
    logger.info(f"📊 Search Metrics:")
    logger.info(f"   Mode: {metrics.search_mode}")
    logger.info(f"   Total Time: {metrics.processing_time:.3f}s")

    if metrics.search_mode == "hybrid":
        logger.info(f"   Dense Time: {metrics.dense_time:.3f}s")
        logger.info(f"   BM25 Time: {metrics.bm25_time:.3f}s")
        logger.info(f"   Fusion Time: {metrics.fusion_time:.3f}s")

    logger.info(f"   Results: {metrics.results_count}")
    logger.info(f"   Top Score: {metrics.top_score:.1f}/100")

# Example usage
metrics = SearchMetrics(
    search_mode=request.search_mode.value,
    processing_time=time.time() - start_time,
    dense_time=dense_time,
    bm25_time=bm25_time,
    fusion_time=fusion_time,
    results_count=len(results),
    top_score=results[0]['score'] if results else 0
)

log_search_metrics(metrics)
```

---

## Summary Checklist

Use this checklist when implementing in your service:

### Schema Layer
- [ ] Define `SearchMode` enum with `HYBRID`, `SEMANTIC`, `BM25`
- [ ] Add `search_mode` field to request schemas with default `HYBRID`
- [ ] Update example requests in schema `model_config`
- [ ] Import enum in all relevant files

### Endpoint Layer
- [ ] Import `SearchMode` in query endpoint
- [ ] Add conditional logic for each search mode
- [ ] Implement `search_semantic_only()` function
- [ ] Implement `search_bm25_only()` function
- [ ] Implement `search_hybrid()` function with RRF
- [ ] Normalize all scores to 0-100 range
- [ ] Update logging to show selected mode

### Handler Layer (if using orchestrator)
- [ ] Add `search_mode` parameter to handler `search()` method
- [ ] Pass `search_mode` in HTTP request payload
- [ ] Update orchestrator to pass `search_mode.value` to handlers

### Testing
- [ ] Unit tests for enum values
- [ ] Unit tests for default mode
- [ ] Integration tests for each mode
- [ ] A/B comparison tests
- [ ] Performance benchmarks

### Frontend
- [ ] UI component for mode selection
- [ ] Helpful descriptions for each mode
- [ ] Visual feedback showing which mode was used
- [ ] Optional: Smart auto-selection based on query type

### Documentation
- [ ] Update API documentation with search_mode parameter
- [ ] Add examples for each mode
- [ ] Document score interpretation per mode
- [ ] Create performance comparison table

---

## Additional Resources

- **BM25 Algorithm**: [Wikipedia - Okapi BM25](https://en.wikipedia.org/wiki/Okapi_BM25)
- **RRF Fusion**: [Reciprocal Rank Fusion Paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- **Milvus BM25 Docs**: [Milvus Full-Text Search](https://milvus.io/docs/full-text-search.md)
- **Embedding Models**: [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)

---

## Questions?

If you encounter issues implementing this in your service:

1. **Check Milvus Version**: BM25 requires Milvus 2.5.0+
2. **Verify Schema**: Collection must have both `embedding` (dense) and `sparse` (BM25) fields
3. **Test Each Mode Separately**: Isolate which part is failing
4. **Check Logs**: Search for "SEARCH MODE" in logs to confirm mode selection
5. **Score Validation**: Ensure all scores are 0-100 range

**Pro Tip**: Start with just `semantic` mode, then add `bm25`, finally implement `hybrid` with RRF fusion. This incremental approach makes debugging easier.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-31
**Authors**: OneDocs Team
**Milvus Version**: 2.5.16
**Python Version**: 3.9+
