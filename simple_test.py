#!/usr/bin/env python3
"""
Simple RAG pipeline tester without complex dependencies
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from pathlib import Path

def test_pdf_parsing(pdf_path: str):
    """Test PDF parsing only"""
    print("🔍 Step 1: PDF Parsing Test")
    print("-" * 50)
    
    try:
        import pymupdf
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        print(f"📄 PDF dosyası okundu: {len(pdf_data)} bytes")
        
        # Parse PDF with PyMuPDF
        pdf_stream = io.BytesIO(pdf_data)
        doc = pymupdf.open(stream=pdf_stream, filetype="pdf")
        
        print(f"📑 Sayfa sayısı: {len(doc)}")
        
        # Extract metadata
        metadata = doc.metadata
        print(f"📊 Başlık: {metadata.get('title', 'Başlık yok')}")
        print(f"📅 Oluşturma tarihi: {metadata.get('creationDate', 'Tarih yok')}")
        
        # Extract first page text
        if len(doc) > 0:
            first_page = doc[0]
            text = first_page.get_text("text")
            print(f"📝 İlk sayfa (ilk 300 karakter):")
            print(text[:300] + "...")
        
        doc.close()
        
        return True
        
    except Exception as e:
        print(f"❌ PDF parsing hatası: {e}")
        return False

def test_simple_chunking(pdf_path: str):
    """Test simple text chunking"""
    print("\n🔧 Step 2: Simple Text Chunking Test")  
    print("-" * 50)
    
    try:
        import pymupdf
        import io
        import hashlib
        import re
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Parse PDF
        pdf_stream = io.BytesIO(pdf_data)
        doc = pymupdf.open(stream=pdf_stream, filetype="pdf")
        
        all_text = ""
        pages_text = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text("text")
            pages_text.append({
                "page_number": page_num + 1,
                "text": page_text,
                "char_count": len(page_text)
            })
            all_text += page_text + "\n\n"
        
        doc.close()
        
        print(f"📄 Toplam metin uzunluğu: {len(all_text)} karakter")
        
        # Simple paragraph-based chunking
        paragraphs = re.split(r'\n\s*\n', all_text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        print(f"📋 Paragraf sayısı: {len(paragraphs)}")
        
        # Create chunks (group paragraphs)
        chunks = []
        current_chunk = ""
        chunk_size_limit = 2000  # characters
        
        for i, paragraph in enumerate(paragraphs):
            if len(current_chunk) + len(paragraph) <= chunk_size_limit:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append({
                        "chunk_id": f"chunk_{len(chunks):04d}",
                        "text": current_chunk.strip(),
                        "char_count": len(current_chunk.strip()),
                        "token_estimate": len(current_chunk.strip()) // 4
                    })
                current_chunk = paragraph + "\n\n"
        
        # Add last chunk
        if current_chunk:
            chunks.append({
                "chunk_id": f"chunk_{len(chunks):04d}",
                "text": current_chunk.strip(),
                "char_count": len(current_chunk.strip()),
                "token_estimate": len(current_chunk.strip()) // 4
            })
        
        print(f"📦 Oluşturulan chunk sayısı: {len(chunks)}")
        
        # Show first few chunks
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n📋 Chunk {i+1}:")
            print(f"   ID: {chunk['chunk_id']}")
            print(f"   Karakter: {chunk['char_count']}")
            print(f"   Token (tahmini): {chunk['token_estimate']}")
            print(f"   Metin (ilk 150 karakter): {chunk['text'][:150]}...")
        
        return chunks
        
    except Exception as e:
        print(f"❌ Chunking hatası: {e}")
        return None

def test_simple_embedding(chunks):
    """Test simple embedding simulation"""
    print("\n🤖 Step 3: Embedding Simulation Test")
    print("-" * 50)
    
    try:
        import numpy as np
        
        print("📊 Embedding modelini simüle ediyoruz...")
        print("🔧 Model: intfloat/multilingual-e5-small (simulated)")
        print("📏 Dimension: 384")
        
        embeddings = []
        for chunk in chunks[:3]:  # Only first 3 chunks
            # Simulate embedding - in real scenario this would be actual embedding
            np.random.seed(hash(chunk['text']) % (2**32))  # Reproducible random based on text
            embedding = np.random.normal(0, 1, 384)  # 384 dimensions
            embedding = embedding / np.linalg.norm(embedding)  # Normalize
            embeddings.append(embedding)
        
        print(f"✅ {len(embeddings)} chunk için embedding simüle edildi!")
        print(f"📊 Embedding shape: {len(embeddings)} x {len(embeddings[0]) if embeddings else 0}")
        
        if embeddings:
            print(f"🔍 İlk embedding (ilk 10 değer): {embeddings[0][:10]}")
            print(f"📏 Norm: {np.linalg.norm(embeddings[0]):.3f} (normalized)")
        
        return embeddings
        
    except Exception as e:
        print(f"❌ Embedding simülasyonu hatası: {e}")
        return None

def save_results(chunks, embeddings, document_id="test_doc_001"):
    """Save results to JSON file"""
    print("\n💾 Step 4: Sonuçları Kaydetme")
    print("-" * 50)
    
    try:
        output_dir = Path("./test_output")
        output_dir.mkdir(exist_ok=True)
        
        # Combine chunks and embeddings
        results_data = {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "embedding_dimension": len(embeddings[0]) if embeddings else 0,
            "chunks": []
        }
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_data = {
                **chunk,
                "embedding": embedding.tolist(),  # Convert numpy array to list
                "embedding_norm": float(np.linalg.norm(embedding))
            }
            results_data["chunks"].append(chunk_data)
        
        # Save to JSON
        output_file = output_dir / f"{document_id}_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Sonuçlar kaydedildi: {output_file}")
        print(f"📁 Dosya boyutu: {output_file.stat().st_size / 1024:.2f} KB")
        
        # Also create a summary
        summary = {
            "document_info": {
                "document_id": document_id,
                "total_chunks": len(chunks),
                "avg_chunk_size": sum(c['char_count'] for c in chunks) / len(chunks),
                "total_characters": sum(c['char_count'] for c in chunks)
            },
            "embedding_info": {
                "model": "intfloat/multilingual-e5-small (simulated)",
                "dimension": len(embeddings[0]) if embeddings else 0,
                "total_embeddings": len(embeddings)
            }
        }
        
        summary_file = output_dir / f"{document_id}_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"📋 Özet kaydedildi: {summary_file}")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Kaydetme hatası: {e}")
        return None

def main():
    print("🚀 Simple RAG Pipeline Test")
    print("=" * 50)
    
    # PDF dosyası yolu
    pdf_path = input("📁 PDF dosya yolunu girin: ").strip()
    
    if not os.path.exists(pdf_path):
        print(f"❌ Dosya bulunamadı: {pdf_path}")
        return
    
    # Step 1: PDF Parsing
    if not test_pdf_parsing(pdf_path):
        return
    
    # Step 2: Simple Chunking
    chunks = test_simple_chunking(pdf_path)
    if not chunks:
        return
    
    # Step 3: Embedding Simulation
    embeddings = test_simple_embedding(chunks)
    if not embeddings:
        return
    
    # Step 4: Save Results
    output_file = save_results(chunks, embeddings)
    
    print("\n" + "=" * 60)
    print("✅ Tüm testler tamamlandı!")
    print(f"📊 Sonuç: {len(chunks)} chunk → {len(embeddings)} embedding")
    if output_file:
        print(f"💾 Çıktı dosyası: {output_file}")
    print("=" * 60)
    print("\n🎯 Sonraki adımlar:")
    print("1. 🤖 Gerçek embedding modelini test et")
    print("2. 🔍 Similarity search implementasyonu")
    print("3. 🔗 Milvus entegrasyonu")
    print("4. 💬 LLM cevap üretimi")

if __name__ == "__main__":
    import io
    import numpy as np
    main()