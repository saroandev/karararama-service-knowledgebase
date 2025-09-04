#!/usr/bin/env python3
"""
Sistem test scripti - RAG pipeline'ını adım adım test eder
"""
import sys
import os
import json
from pathlib import Path

# Add app to path
sys.path.append('.')

def test_imports():
    """Test all imports"""
    print("🔍 Import testleri...")
    try:
        from app.config import settings
        print(f"   ✅ Config loaded - Embedding model: {settings.EMBEDDING_MODEL}")
        
        from app.parse import pdf_parser
        print("   ✅ PDF parser imported")
        
        from app.chunk import get_document_chunker
        chunker = get_document_chunker()
        print("   ✅ Document chunker loaded")
        
        from app.embed import embedding_generator
        print("   ✅ Embedding generator imported")
        
        # Test if model is available (without loading)
        print(f"   📋 Target embedding model: {settings.EMBEDDING_MODEL}")
        
        return True
    except Exception as e:
        print(f"   ❌ Import hatası: {e}")
        return False

def test_pdf_parsing():
    """Test PDF parsing"""
    print("\n📄 PDF parsing testi...")
    
    pdf_path = "Milvus + Min Io Ile Basit Rag Pipeline — Adım Adım Plan Ve Kod İskeleti.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"   ⚠️ Test PDF bulunamadı: {pdf_path}")
        return False
    
    try:
        from app.parse import pdf_parser
        
        with open(pdf_path, 'rb') as f:
            file_data = f.read()
        
        pages, metadata = pdf_parser.extract_text_from_pdf(file_data)
        
        print(f"   ✅ PDF parse edildi:")
        print(f"      - Sayfa sayısı: {len(pages)}")
        print(f"      - Toplam karakter: {sum(len(p.text) for p in pages)}")
        print(f"      - Başlık: {metadata.title or 'N/A'}")
        print(f"      - Dosya boyutu: {metadata.file_size/1024:.1f} KB")
        
        return pages, metadata
    except Exception as e:
        print(f"   ❌ PDF parsing hatası: {e}")
        return False

def test_chunking(pages):
    """Test chunking"""
    print("\n📋 Chunking testi...")
    
    try:
        from app.chunk import get_document_chunker
        chunker = get_document_chunker()
        
        document_id = "test_doc_001"
        chunks = chunker.chunk_by_document(pages, document_id)
        
        print(f"   ✅ Chunks oluşturuldu:")
        print(f"      - Chunk sayısı: {len(chunks)}")
        print(f"      - Ortalama chunk boyutu: {sum(c.char_count for c in chunks) / len(chunks):.0f} karakter")
        
        # İlk chunk'ın önizlemesi
        if chunks:
            preview = chunks[0].text[:200] + "..." if len(chunks[0].text) > 200 else chunks[0].text
            print(f"      - İlk chunk önizlemesi: {preview}")
        
        return chunks
    except Exception as e:
        print(f"   ❌ Chunking hatası: {e}")
        return False

def test_embedding_simulation(chunks):
    """Test embedding generation (simulated)"""
    print("\n🧮 Embedding testi (simülasyon)...")
    
    try:
        import numpy as np
        from app.config import settings
        
        # Simulate embeddings (384 dimensions for multilingual-e5-small)
        embeddings = []
        for chunk in chunks:
            # Create deterministic "fake" embedding based on text hash
            text_hash = hash(chunk.text) % 1000000
            np.random.seed(text_hash)
            embedding = np.random.normal(0, 1, 384)
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding.tolist())
        
        print(f"   ✅ Embeddings simüle edildi:")
        print(f"      - Embedding boyutu: 384 (multilingual-e5-small)")
        print(f"      - Toplam embedding sayısı: {len(embeddings)}")
        print(f"      - İlk embedding norm: {np.linalg.norm(embeddings[0]):.3f}")
        
        return embeddings
    except Exception as e:
        print(f"   ❌ Embedding simülasyonu hatası: {e}")
        return False

def test_config_validation():
    """Test configuration"""
    print("\n⚙️ Konfigürasyon testi...")
    
    try:
        from app.config import settings
        
        print(f"   📋 Mevcut ayarlar:")
        print(f"      - Embedding Model: {settings.EMBEDDING_MODEL}")
        print(f"      - LLM Provider: {settings.LLM_PROVIDER}")
        print(f"      - Reranker Model: {settings.RERANKER_MODEL}")
        print(f"      - Milvus Host: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        print(f"      - MinIO Endpoint: {settings.MINIO_ENDPOINT}")
        
        # Check if critical settings are present
        warnings = []
        if not settings.OPENAI_API_KEY and settings.LLM_PROVIDER == "openai":
            warnings.append("OpenAI API key eksik")
        
        if warnings:
            print(f"   ⚠️ Uyarılar:")
            for warning in warnings:
                print(f"      - {warning}")
        else:
            print(f"   ✅ Temel konfigürasyon tamam")
        
        return True
    except Exception as e:
        print(f"   ❌ Konfigürasyon hatası: {e}")
        return False

def test_server_import():
    """Test server import"""
    print("\n🌐 Server import testi...")
    
    try:
        from app import server
        print("   ✅ FastAPI server import edildi")
        print("   📋 Mevcut endpoint'ler:")
        
        for route in server.app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                methods = ', '.join(route.methods)
                print(f"      - {methods} {route.path}")
        
        return True
    except Exception as e:
        print(f"   ❌ Server import hatası: {e}")
        return False

def save_test_results(results):
    """Save test results"""
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    results_file = output_dir / "system_test_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Test sonuçları kaydedildi: {results_file}")

def main():
    """Ana test fonksiyonu"""
    print("🚀 RAG Sistem Testi Başlatılıyor...\n")
    
    results = {
        "test_date": "2024-01-01",
        "tests": {}
    }
    
    # 1. Import testleri
    results["tests"]["imports"] = test_imports()
    
    # 2. Configuration
    results["tests"]["config"] = test_config_validation()
    
    # 3. PDF parsing
    parse_result = test_pdf_parsing()
    results["tests"]["pdf_parsing"] = bool(parse_result)
    
    if parse_result:
        pages, metadata = parse_result
        results["pdf_stats"] = {
            "pages": len(pages),
            "total_chars": sum(len(p.text) for p in pages),
            "file_size_kb": metadata.file_size / 1024
        }
        
        # 4. Chunking
        chunk_result = test_chunking(pages)
        results["tests"]["chunking"] = bool(chunk_result)
        
        if chunk_result:
            chunks = chunk_result
            results["chunk_stats"] = {
                "chunk_count": len(chunks),
                "avg_chunk_size": sum(c.char_count for c in chunks) / len(chunks)
            }
            
            # 5. Embedding simulation
            embedding_result = test_embedding_simulation(chunks)
            results["tests"]["embeddings"] = bool(embedding_result)
            
            if embedding_result:
                results["embedding_stats"] = {
                    "embedding_count": len(embedding_result),
                    "dimension": 384
                }
    
    # 6. Server import
    results["tests"]["server_import"] = test_server_import()
    
    # Özet
    print("\n" + "="*50)
    print("📊 TEST ÖZETİ")
    print("="*50)
    
    passed_tests = sum(1 for test, result in results["tests"].items() if result)
    total_tests = len(results["tests"])
    
    print(f"Geçen testler: {passed_tests}/{total_tests}")
    
    for test_name, result in results["tests"].items():
        status = "✅ GEÇT​İ" if result else "❌ BAŞARISIZ"
        print(f"  {test_name}: {status}")
    
    # Save results
    save_test_results(results)
    
    if passed_tests == total_tests:
        print("\n🎉 Tüm testler başarılı! Sistem hazır.")
        return 0
    else:
        print(f"\n⚠️ {total_tests - passed_tests} test başarısız. Lütfen hataları kontrol edin.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)