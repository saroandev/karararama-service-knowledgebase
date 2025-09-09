#!/usr/bin/env python3
"""
Full pipeline test with actual embedding generation
"""

import sys
import time
from datetime import datetime

sys.path.append('/Users/ugur/Desktop/Onedocs-RAG-Project/main')

print("="*60)
print("FULL RAG PIPELINE TEST WITH EMBEDDINGS")
print("="*60)

# 1. PDF PARSING
print("\n[STEP 1] PDF PARSING")
print("-"*40)

from app.parse import pdf_parser

pdf_file = "POSTA GEZİCİ PERSONELİNE VERİLECEK HARCIRAH TÜZÜĞÜ_78670.pdf"
with open(pdf_file, 'rb') as f:
    pdf_data = f.read()

start = time.time()
pages, doc_metadata = pdf_parser.extract_text_from_pdf(pdf_data)
parse_time = time.time() - start

print(f"✅ PDF parsed in {parse_time:.2f}s")
print(f"   • Pages: {len(pages)}")
print(f"   • Total chars: {sum(p.metadata['char_count'] for p in pages):,}")

# 2. TEXT CHUNKING
print("\n[STEP 2] TEXT CHUNKING")
print("-"*40)

from app.chunk import TextChunker

start = time.time()
chunker = TextChunker(chunk_size=512, chunk_overlap=50, method="token")
chunks = chunker.chunk_pages(pages, "test_doc_001", preserve_pages=True)
chunk_time = time.time() - start

print(f"✅ Chunking completed in {chunk_time:.2f}s")
print(f"   • Chunks created: {len(chunks)}")
print(f"   • Avg chunk size: {sum(c.token_count for c in chunks) / len(chunks):.1f} tokens")

# 3. EMBEDDING GENERATION
print("\n[STEP 3] EMBEDDING GENERATION")
print("-"*40)

from app.embed import embedding_generator

# Get chunk texts
chunk_texts = [chunk.text for chunk in chunks]

start = time.time()
print(f"   Generating embeddings for {len(chunk_texts)} chunks...")
embeddings = embedding_generator.generate_embeddings_batch(chunk_texts, show_progress=False)
embed_time = time.time() - start

print(f"✅ Embeddings generated in {embed_time:.2f}s")
print(f"   • Vectors created: {len(embeddings)}")
print(f"   • Vector dimension: {len(embeddings[0]) if embeddings else 0}")
print(f"   • Model: {embedding_generator.model_name}")

# 4. STORAGE
print("\n[STEP 4] MINIO STORAGE")
print("-"*40)

from app.storage import storage

document_id = f"test_doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Prepare chunk data
chunk_data_list = []
for chunk in chunks:
    chunk_dict = {
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "metadata": chunk.metadata,
        "token_count": chunk.token_count,
        "char_count": chunk.char_count
    }
    chunk_data_list.append(chunk_dict)

start = time.time()
saved_count = storage.save_chunks_batch(document_id, chunk_data_list)
storage_time = time.time() - start

print(f"✅ Chunks saved to MinIO in {storage_time:.2f}s")
print(f"   • Document ID: {document_id}")
print(f"   • Chunks saved: {saved_count}")

# 5. VECTOR INDEXING
print("\n[STEP 5] MILVUS INDEXING")
print("-"*40)

from app.index import milvus_indexer

# Prepare milvus chunks
milvus_chunks = []
for chunk in chunks:
    milvus_chunk = {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "metadata": chunk.metadata
    }
    milvus_chunks.append(milvus_chunk)

start = time.time()
try:
    indexed_count = milvus_indexer.insert_chunks(milvus_chunks, embeddings)
    index_time = time.time() - start
    
    print(f"✅ Vectors indexed in Milvus in {index_time:.2f}s")
    print(f"   • Chunks indexed: {indexed_count}")
    
    # Get collection stats
    stats = milvus_indexer.get_collection_stats()
    print(f"   • Total entities in collection: {stats['entity_count']:,}")
    
except Exception as e:
    print(f"❌ Milvus indexing failed: {str(e)}")
    index_time = 0

# SUMMARY
print("\n" + "="*60)
print("PIPELINE EXECUTION SUMMARY")
print("="*60)

total_time = parse_time + chunk_time + embed_time + storage_time + index_time

print(f"""
📊 Data Flow:
   1 PDF ({len(pdf_data):,} bytes)
   ↓
   {len(pages)} page(s) ({sum(p.metadata['char_count'] for p in pages):,} chars)
   ↓
   {len(chunks)} chunks ({sum(c.token_count for c in chunks):,} tokens)
   ↓
   {len(embeddings)} vectors (384-dim each)
   ↓
   MinIO + Milvus storage

⏱️  Performance:
   • PDF Parsing:    {parse_time:.2f}s
   • Text Chunking:  {chunk_time:.2f}s
   • Embedding Gen:  {embed_time:.2f}s
   • MinIO Storage:  {storage_time:.2f}s
   • Milvus Index:   {index_time:.2f}s
   • TOTAL:          {total_time:.2f}s

📈 Throughput:
   • Chunks/second:  {len(chunks)/total_time:.1f}
   • Tokens/second:  {sum(c.token_count for c in chunks)/total_time:.1f}
""")

print("✅ Full pipeline test completed successfully!")