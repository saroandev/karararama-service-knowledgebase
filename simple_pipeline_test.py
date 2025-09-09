#!/usr/bin/env python3
"""
Simplified pipeline test without heavy model loading
"""

import sys
import json
from pathlib import Path

sys.path.append('/Users/ugur/Desktop/Onedocs-RAG-Project/main')

print("="*60)
print("SIMPLIFIED RAG PIPELINE TEST")
print("="*60)

# 1. PDF PARSING
print("\n1. PDF PARSING")
print("-"*40)

from app.parse import pdf_parser

pdf_file = "POSTA GEZİCİ PERSONELİNE VERİLECEK HARCIRAH TÜZÜĞÜ_78670.pdf"
with open(pdf_file, 'rb') as f:
    pdf_data = f.read()

pages, doc_metadata = pdf_parser.extract_text_from_pdf(pdf_data)

print(f"✅ PDF parsed successfully")
print(f"   • File size: {len(pdf_data):,} bytes")
print(f"   • Pages found: {len(pages)}")
print(f"   • Document title: {doc_metadata.title or 'Not found'}")
print(f"   • Page count: {doc_metadata.page_count}")
print(f"   • Document hash: {doc_metadata.document_hash[:16]}...")

if pages:
    total_chars = sum(p.metadata['char_count'] for p in pages)
    total_words = sum(p.metadata['word_count'] for p in pages)
    print(f"   • Total characters: {total_chars:,}")
    print(f"   • Total words: {total_words:,}")
    
    # Show first 200 chars
    print(f"\n   First 200 characters of text:")
    print(f"   {pages[0].text[:200]}...")

# 2. TEXT CHUNKING (Simple)
print("\n2. TEXT CHUNKING")
print("-"*40)

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Combine all page texts
full_text = "\n\n".join(page.text for page in pages)
print(f"   • Combined text length: {len(full_text):,} characters")

# Simple character-based chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,  # characters, not tokens
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""]
)

text_chunks = splitter.split_text(full_text)
print(f"✅ Text chunked successfully")
print(f"   • Chunks created: {len(text_chunks)}")
print(f"   • Average chunk size: {sum(len(c) for c in text_chunks) / len(text_chunks):.1f} chars")

# Show first 3 chunks
print(f"\n   First 3 chunks:")
for i, chunk in enumerate(text_chunks[:3]):
    print(f"   Chunk {i+1} ({len(chunk)} chars): {chunk[:80]}...")

# 3. STORAGE CONNECTION TEST
print("\n3. MINIO STORAGE TEST")
print("-"*40)

try:
    from app.storage import storage
    
    # List existing documents
    documents = storage.list_documents()
    print(f"✅ MinIO connected successfully")
    print(f"   • Documents in storage: {len(documents)}")
    
    # Show last 3 documents
    if documents:
        print(f"\n   Last 3 documents:")
        for doc in documents[-3:]:
            print(f"   • {doc['document_id']} ({doc['chunk_count']} chunks)")
    
except Exception as e:
    print(f"❌ MinIO connection failed: {str(e)}")

# 4. MILVUS CONNECTION TEST
print("\n4. MILVUS INDEX TEST")
print("-"*40)

try:
    from app.index import milvus_indexer
    
    # Get collection stats
    stats = milvus_indexer.get_collection_stats()
    print(f"✅ Milvus connected successfully")
    print(f"   • Collection: {milvus_indexer.collection_name}")
    print(f"   • Total entities: {stats['entity_count']:,}")
    
except Exception as e:
    print(f"❌ Milvus connection failed: {str(e)}")

# 5. SUMMARY
print("\n" + "="*60)
print("PIPELINE DATA FLOW SUMMARY")
print("="*60)

print(f"""
Input: 1 PDF file ({len(pdf_data):,} bytes)
   ↓
Parse: {len(pages)} page(s) → {total_chars:,} characters
   ↓
Chunk: {len(text_chunks)} chunks (~500 chars each)
   ↓
Embed: {len(text_chunks)} vectors (would be generated)
   ↓
Store: MinIO (chunks) + Milvus (vectors)
""")

print("✅ Basic pipeline test completed!")
print("\nNote: This test uses simple character-based chunking.")
print("Production uses token-based chunking with embedding model.")