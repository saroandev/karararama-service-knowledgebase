#!/usr/bin/env python3
"""
Step-by-step RAG pipeline tester
Milvus olmadan her adımı test ederiz
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.parse import pdf_parser
from app.chunk import DocumentBasedChunker
from app.embed import EmbeddingGenerator
from app.storage import storage
import json
from pathlib import Path

def test_pdf_parsing(pdf_path: str):
    """Test PDF parsing"""
    print("🔍 Step 1: PDF Parsing Test")
    print("-" * 50)
    
    try:
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        print(f"📄 PDF dosyası okundu: {len(pdf_data)} bytes")
        
        # Parse PDF
        pages, metadata = pdf_parser.extract_text_from_pdf(pdf_data)
        
        print(f"📑 Sayfa sayısı: {len(pages)}")
        print(f"📊 Metadata: {metadata.title or 'Başlık yok'}")
        print(f"📝 İlk sayfa (ilk 200 karakter):")
        if pages:
            print(pages[0].text[:200] + "...")
        
        return pages, metadata
        
    except Exception as e:
        print(f"❌ PDF parsing hatası: {e}")
        return None, None

def test_document_chunking(pages, document_id="test_doc_001"):
    """Test document-based chunking"""
    print("\n🔧 Step 2: Document-Based Chunking Test")
    print("-" * 50)
    
    try:
        chunker = DocumentBasedChunker(chunk_size=512, chunk_overlap=50)
        chunks = chunker.chunk_by_document(pages, document_id)
        
        print(f"📦 Oluşturulan chunk sayısı: {len(chunks)}")
        
        for i, chunk in enumerate(chunks[:3]):  # İlk 3 chunk'ı göster
            print(f"\n📋 Chunk {i+1}:")
            print(f"   ID: {chunk.chunk_id}")
            print(f"   Sayfa: {chunk.metadata.get('page_number', 'N/A')}")
            print(f"   Token sayısı: {chunk.token_count}")
            print(f"   Metin (ilk 150 karakter): {chunk.text[:150]}...")
        
        return chunks
        
    except Exception as e:
        print(f"❌ Chunking hatası: {e}")
        return None

def test_embedding_generation(chunks):
    """Test embedding generation"""
    print("\n🤖 Step 3: Embedding Generation Test")
    print("-" * 50)
    
    try:
        # Initialize embedding generator
        embedder = EmbeddingGenerator()
        
        print(f"🧠 Model: {embedder.model_name}")
        print(f"📏 Dimension: {embedder.dimension}")
        print(f"🔧 Device: {embedder.device}")
        
        # Test with first few chunks
        test_chunks = chunks[:3] if len(chunks) >= 3 else chunks
        chunk_texts = [chunk.text for chunk in test_chunks]
        
        print(f"\n⚙️ {len(chunk_texts)} chunk için embedding üretiliyor...")
        embeddings = embedder.generate_embeddings_batch(chunk_texts, show_progress=True)
        
        print(f"✅ Embedding üretimi tamamlandı!")
        print(f"📊 Embedding shape: {len(embeddings)} x {len(embeddings[0]) if embeddings else 0}")
        
        # İlk embedding'in ilk 10 değerini göster
        if embeddings:
            print(f"🔍 İlk embedding (ilk 10 değer): {embeddings[0][:10]}")
        
        return embeddings
        
    except Exception as e:
        print(f"❌ Embedding hatası: {e}")
        return None

def test_storage_operations(chunks, embeddings, document_id="test_doc_001"):
    """Test storage operations (MinIO simulation)"""
    print("\n💾 Step 4: Storage Test (MinIO Simulation)")
    print("-" * 50)
    
    try:
        # Sadece dosya sistemine kaydet (MinIO yerine)
        output_dir = Path("./test_output")
        output_dir.mkdir(exist_ok=True)
        
        # Save chunks
        chunks_data = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_data = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "token_count": chunk.token_count,
                "char_count": chunk.char_count,
                "embedding": embedding.tolist()  # JSON için list'e çevir
            }
            chunks_data.append(chunk_data)
        
        # Save to JSON
        output_file = output_dir / f"{document_id}_chunks.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {len(chunks_data)} chunk kaydedildi: {output_file}")
        print(f"📁 Dosya boyutu: {output_file.stat().st_size / 1024:.2f} KB")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Storage hatası: {e}")
        return None

def main():
    print("🚀 RAG Pipeline Step-by-Step Test")
    print("=" * 60)
    
    # PDF dosyası yolu - bunu güncelleyin
    pdf_path = input("📁 PDF dosya yolunu girin: ").strip()
    
    if not os.path.exists(pdf_path):
        print(f"❌ Dosya bulunamadı: {pdf_path}")
        return
    
    # Step 1: PDF Parsing
    pages, metadata = test_pdf_parsing(pdf_path)
    if not pages:
        return
    
    # Step 2: Document Chunking
    chunks = test_document_chunking(pages)
    if not chunks:
        return
    
    # Step 3: Embedding Generation
    embeddings = test_embedding_generation(chunks)
    if not embeddings:
        return
    
    # Step 4: Storage Test
    output_file = test_storage_operations(chunks, embeddings)
    
    print("\n" + "=" * 60)
    print("✅ Tüm testler tamamlandı!")
    print(f"📊 Sonuç: {len(pages)} sayfa → {len(chunks)} chunk → {len(embeddings)} embedding")
    if output_file:
        print(f"💾 Çıktı dosyası: {output_file}")
    print("=" * 60)

if __name__ == "__main__":
    main()