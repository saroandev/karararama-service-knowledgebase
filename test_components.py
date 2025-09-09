#!/usr/bin/env python3
"""
Component-by-component test of the RAG pipeline
Tests each component individually to understand the data flow
"""

import sys
import json
from pathlib import Path

# Python path'i ayarla
sys.path.append('/Users/ugur/Desktop/Onedocs-RAG-Project/main')

# Renkli output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{title}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")

# PDF dosyası
PDF_FILE = "POSTA GEZİCİ PERSONELİNE VERİLECEK HARCIRAH TÜZÜĞÜ_78670.pdf"

# =============================================================================
# TEST 1: PDF PARSING
# =============================================================================
def test_pdf_parsing():
    print_section("TEST 1: PDF PARSING")
    
    from app.parse import pdf_parser
    
    # PDF'i oku
    with open(PDF_FILE, 'rb') as f:
        pdf_data = f.read()
    
    print_info(f"PDF boyutu: {len(pdf_data):,} bytes")
    
    # Parse et
    try:
        pages, doc_metadata = pdf_parser.extract_text_from_pdf(pdf_data)
        
        print_success(f"PDF parse edildi: {len(pages)} sayfa bulundu")
        
        # Doküman metadata'sını göster
        print(f"\n{Colors.BOLD}Doküman Metadata:{Colors.ENDC}")
        print(f"  • Başlık: {doc_metadata.title or 'Yok'}")
        print(f"  • Yazar: {doc_metadata.author or 'Yok'}")
        print(f"  • Sayfa sayısı: {doc_metadata.page_count}")
        print(f"  • Dosya boyutu: {doc_metadata.file_size:,} bytes")
        print(f"  • Oluşturma tarihi: {doc_metadata.creation_date or 'Yok'}")
        print(f"  • Hash: {doc_metadata.document_hash[:16]}...")
        
        # İlk sayfa bilgileri
        if pages:
            first_page = pages[0]
            print(f"\n{Colors.BOLD}İlk Sayfa Bilgileri:{Colors.ENDC}")
            print(f"  • Sayfa no: {first_page.page_number}")
            print(f"  • Karakter sayısı: {first_page.metadata['char_count']:,}")
            print(f"  • Kelime sayısı: {first_page.metadata['word_count']:,}")
            print(f"  • Resim var mı: {first_page.metadata.get('has_images', False)}")
            print(f"  • Tablo var mı: {first_page.metadata.get('has_tables', False)}")
            
            # İlk 200 karakter
            print(f"\n{Colors.BOLD}İlk sayfa metni (ilk 200 karakter):{Colors.ENDC}")
            print(f"{first_page.text[:200]}...")
        
        return pages, doc_metadata
        
    except Exception as e:
        print_error(f"Parse hatası: {str(e)}")
        return None, None

# =============================================================================
# TEST 2: TEXT CHUNKING
# =============================================================================
def test_chunking(pages):
    print_section("TEST 2: TEXT CHUNKING")
    
    if not pages:
        print_error("Sayfa verisi yok, chunking yapılamaz")
        return None
    
    from app.chunk import TextChunker
    
    # Chunker oluştur
    chunker = TextChunker(
        chunk_size=512,
        chunk_overlap=50,
        method="token"
    )
    
    print_info(f"Chunk parametreleri: size={chunker.chunk_size}, overlap={chunker.chunk_overlap}, method={chunker.method}")
    
    # Chunk'la
    try:
        document_id = "test_doc_001"
        chunks = chunker.chunk_pages(pages, document_id, preserve_pages=True)
        
        print_success(f"Chunking tamamlandı: {len(chunks)} chunk oluşturuldu")
        
        # İstatistikler
        total_tokens = sum(c.token_count for c in chunks)
        total_chars = sum(c.char_count for c in chunks)
        avg_tokens = total_tokens / len(chunks) if chunks else 0
        
        print(f"\n{Colors.BOLD}Chunk İstatistikleri:{Colors.ENDC}")
        print(f"  • Toplam chunk: {len(chunks)}")
        print(f"  • Toplam token: {total_tokens:,}")
        print(f"  • Toplam karakter: {total_chars:,}")
        print(f"  • Ortalama token/chunk: {avg_tokens:.1f}")
        
        # İlk chunk
        if chunks:
            first_chunk = chunks[0]
            print(f"\n{Colors.BOLD}İlk Chunk Bilgileri:{Colors.ENDC}")
            print(f"  • ID: {first_chunk.chunk_id}")
            print(f"  • Index: {first_chunk.chunk_index}")
            print(f"  • Token sayısı: {first_chunk.token_count}")
            print(f"  • Karakter sayısı: {first_chunk.char_count}")
            print(f"  • Sayfa no: {first_chunk.metadata.get('page_number', 'N/A')}")
            
            print(f"\n{Colors.BOLD}İlk chunk metni (ilk 150 karakter):{Colors.ENDC}")
            print(f"{first_chunk.text[:150]}...")
        
        return chunks
        
    except Exception as e:
        print_error(f"Chunking hatası: {str(e)}")
        return None

# =============================================================================
# TEST 3: EMBEDDING GENERATION
# =============================================================================
def test_embedding(chunks):
    print_section("TEST 3: EMBEDDING GENERATION")
    
    if not chunks:
        print_error("Chunk verisi yok, embedding yapılamaz")
        return None
    
    from app.embed import embedding_generator
    
    # İlk 3 chunk için test
    test_chunks = chunks[:3]
    texts = [chunk.text for chunk in test_chunks]
    
    print_info(f"İlk {len(test_chunks)} chunk için embedding üretiliyor...")
    
    try:
        embeddings = embedding_generator.generate_embeddings_batch(texts, show_progress=True)
        
        print_success(f"Embedding üretildi: {len(embeddings)} vektör")
        
        # Embedding bilgileri
        if embeddings:
            print(f"\n{Colors.BOLD}Embedding Bilgileri:{Colors.ENDC}")
            print(f"  • Vektör sayısı: {len(embeddings)}")
            print(f"  • Vektör boyutu: {len(embeddings[0])}")
            print(f"  • Model: {embedding_generator.model_name}")
            print(f"  • Device: {embedding_generator.device}")
            
            # İlk vektörden örnek
            print(f"\n{Colors.BOLD}İlk vektör (ilk 10 değer):{Colors.ENDC}")
            print(f"  {embeddings[0][:10]}")
            
            # Vektör istatistikleri
            import numpy as np
            first_vec = np.array(embeddings[0])
            print(f"\n{Colors.BOLD}İlk vektör istatistikleri:{Colors.ENDC}")
            print(f"  • Min: {first_vec.min():.4f}")
            print(f"  • Max: {first_vec.max():.4f}")
            print(f"  • Mean: {first_vec.mean():.4f}")
            print(f"  • Std: {first_vec.std():.4f}")
        
        return embeddings
        
    except Exception as e:
        print_error(f"Embedding hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# TEST 4: MINIO STORAGE
# =============================================================================
def test_storage(chunks):
    print_section("TEST 4: MINIO STORAGE")
    
    if not chunks:
        print_error("Chunk verisi yok, storage test edilemez")
        return None
    
    from app.storage import storage
    
    try:
        # Test document ID
        document_id = "test_doc_storage_001"
        
        # İlk 3 chunk'ı kaydet
        test_chunks = chunks[:3]
        chunk_data_list = []
        
        for chunk in test_chunks:
            chunk_dict = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "token_count": chunk.token_count,
                "char_count": chunk.char_count
            }
            chunk_data_list.append(chunk_dict)
        
        print_info(f"{len(chunk_data_list)} chunk MinIO'ya kaydediliyor...")
        
        # Kaydet
        saved_count = storage.save_chunks_batch(document_id, chunk_data_list)
        
        print_success(f"MinIO'ya kaydedildi: {saved_count} chunk")
        
        # Dokümanları listele
        documents = storage.list_documents()
        print(f"\n{Colors.BOLD}MinIO'daki dokümanlar:{Colors.ENDC}")
        for doc in documents[-5:]:  # Son 5 doküman
            print(f"  • {doc['document_id']} - {doc['chunk_count']} chunks")
        
        return saved_count
        
    except Exception as e:
        print_error(f"Storage hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# TEST 5: MILVUS INDEXING
# =============================================================================
def test_milvus(chunks, embeddings):
    print_section("TEST 5: MILVUS INDEXING")
    
    if not chunks or not embeddings:
        print_error("Chunk veya embedding verisi yok")
        return None
    
    from app.index import milvus_indexer
    
    try:
        # Test için ilk 3 chunk
        test_chunks = chunks[:3]
        test_embeddings = embeddings[:3] if len(embeddings) >= 3 else embeddings
        
        # Milvus chunk formatı
        milvus_chunks = []
        for chunk in test_chunks:
            milvus_chunk = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "metadata": chunk.metadata
            }
            milvus_chunks.append(milvus_chunk)
        
        print_info(f"{len(milvus_chunks)} chunk Milvus'a ekleniyor...")
        
        # İndeksle
        indexed_count = milvus_indexer.insert_chunks(milvus_chunks, test_embeddings)
        
        print_success(f"Milvus'a eklendi: {indexed_count} chunk")
        
        # Collection bilgileri
        stats = milvus_indexer.get_collection_stats()
        print(f"\n{Colors.BOLD}Milvus Collection Bilgileri:{Colors.ENDC}")
        print(f"  • Collection: {milvus_indexer.collection_name}")
        print(f"  • Toplam entity: {stats['entity_count']:,}")
        
        return indexed_count
        
    except Exception as e:
        print_error(f"Milvus hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# MAIN
# =============================================================================
def main():
    print(f"{Colors.BLUE}{Colors.BOLD}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         RAG Pipeline Component Test Suite               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    
    # Test 1: Parsing
    pages, doc_metadata = test_pdf_parsing()
    
    if pages:
        # Test 2: Chunking
        chunks = test_chunking(pages)
        
        if chunks:
            # Test 3: Embedding
            embeddings = test_embedding(chunks)
            
            # Test 4: Storage
            storage_result = test_storage(chunks)
            
            # Test 5: Milvus
            if embeddings:
                milvus_result = test_milvus(chunks, embeddings)
    
    # Özet
    print_section("TEST ÖZETİ")
    
    if pages and chunks:
        print_success("Tüm componentler test edildi!")
        print(f"\n{Colors.BOLD}Pipeline Özeti:{Colors.ENDC}")
        print(f"  1. PDF → {len(pages)} sayfa")
        print(f"  2. {len(pages)} sayfa → {len(chunks)} chunk")
        if embeddings:
            print(f"  3. {len(embeddings)} chunk → {len(embeddings)} vektör")
        print(f"  4. Chunks → MinIO storage")
        print(f"  5. Vectors → Milvus index")
    else:
        print_error("Bazı testler başarısız oldu")

if __name__ == "__main__":
    main()