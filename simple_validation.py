#!/usr/bin/env python3
"""
Basit sistem validasyon scripti - dependency sorunları olmadan
"""
import sys
import os
sys.path.append('.')

def test_basic_imports():
    """Temel import testleri"""
    print("🔍 Temel import testleri...")
    try:
        from app.config import settings
        print(f"   ✅ Config: {settings.EMBEDDING_MODEL}")
        
        from app.parse import pdf_parser
        print("   ✅ PDF Parser")
        
        return True
    except Exception as e:
        print(f"   ❌ Import hatası: {e}")
        return False

def test_pdf_processing():
    """PDF işleme testi"""
    print("\n📄 PDF işleme testi...")
    
    pdf_path = "Milvus + Min Io Ile Basit Rag Pipeline — Adım Adım Plan Ve Kod İskeleti.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"   ⚠️ Test PDF bulunamadı: {pdf_path}")
        return False
    
    try:
        from app.parse import pdf_parser
        
        with open(pdf_path, 'rb') as f:
            file_data = f.read()
        
        pages, metadata = pdf_parser.extract_text_from_pdf(file_data)
        
        print(f"   ✅ PDF işlendi:")
        print(f"      - Sayfa sayısı: {len(pages)}")
        print(f"      - Toplam karakter: {sum(len(p.text) for p in pages)}")
        print(f"      - Dosya boyutu: {metadata.file_size/1024:.1f} KB")
        
        return True
    except Exception as e:
        print(f"   ❌ PDF işleme hatası: {e}")
        return False

def test_document_chunking():
    """Sadece document chunking test et (dependencies olmadan)"""
    print("\n📋 Document chunking testi...")
    
    try:
        from app.chunk import DocumentBasedChunker
        
        # Simple test data
        class MockPage:
            def __init__(self, text, page_number):
                self.text = text
                self.page_number = page_number
                self.metadata = {}
        
        pages = [
            MockPage("Bu ilk sayfa içeriği. Çok uzun olmayan bir metin.", 1),
            MockPage("Bu ikinci sayfa içeriği. Biraz daha uzun bir metin olabilir.", 2)
        ]
        
        chunker = DocumentBasedChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_by_document(pages, "test_doc", {"test": True})
        
        print(f"   ✅ Document chunks oluşturuldu:")
        print(f"      - Chunk sayısı: {len(chunks)}")
        for i, chunk in enumerate(chunks):
            print(f"      - Chunk {i+1}: {len(chunk.text)} karakter, sayfa {chunk.metadata.get('page_number', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"   ❌ Chunking hatası: {e}")
        return False

def test_config():
    """Konfigürasyon testi"""
    print("\n⚙️ Konfigürasyon testi...")
    
    try:
        from app.config import settings
        
        print(f"   📋 Ayarlar:")
        print(f"      - Embedding Model: {settings.EMBEDDING_MODEL}")
        print(f"      - LLM Provider: {settings.LLM_PROVIDER}")
        print(f"      - Milvus Host: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        
        print(f"   ✅ Konfigürasyon OK")
        return True
    except Exception as e:
        print(f"   ❌ Konfigürasyon hatası: {e}")
        return False

def main():
    """Ana test"""
    print("🚀 Basit Sistem Validasyonu\n")
    
    tests = [
        ("basic_imports", test_basic_imports),
        ("config", test_config),
        ("pdf_processing", test_pdf_processing),
        ("document_chunking", test_document_chunking)
    ]
    
    passed = 0
    
    for test_name, test_func in tests:
        if test_func():
            passed += 1
    
    print("\n" + "="*40)
    print(f"📊 Sonuç: {passed}/{len(tests)} test geçti")
    print("="*40)
    
    if passed == len(tests):
        print("🎉 Tüm validasyonlar başarılı!")
        print("\nSonraki adımlar:")
        print("1. pip install -r requirements.txt (dependencies)")
        print("2. docker-compose up (Milvus ve MinIO)")
        print("3. python app/server.py (API server)")
        return 0
    else:
        print("⚠️ Bazı validasyonlar başarısız.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)