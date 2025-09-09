#!/usr/bin/env python3
"""
PDF Ingestion Test Script
Test the entire ingestion pipeline step by step
"""

import sys
import asyncio
from pathlib import Path
import json
from datetime import datetime

# Python path'i ayarla
sys.path.append('/Users/ugur/Desktop/Onedocs-RAG-Project/main')

# Renkli output için
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

async def test_pdf_ingestion():
    """Complete PDF ingestion test"""
    
    from app.ingest import ingestion_pipeline
    
    # PDF dosyasını kontrol et
    pdf_path = Path("POSTA GEZİCİ PERSONELİNE VERİLECEK HARCIRAH TÜZÜĞÜ_78670.pdf")
    
    print_header("PDF INGESTION TEST")
    
    if not pdf_path.exists():
        print_error(f"PDF bulunamadı: {pdf_path}")
        return
    
    # PDF bilgilerini göster
    pdf_size = pdf_path.stat().st_size
    print_info(f"PDF Dosyası: {pdf_path.name}")
    print_info(f"Dosya Boyutu: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")
    
    # PDF'i oku
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
    
    print_success(f"PDF yüklendi: {len(pdf_data):,} bytes")
    
    # Progress callback tanımla
    def progress_callback(progress):
        stage_emoji = {
            "upload": "📤",
            "parsing": "📄",
            "chunking": "✂️",
            "embedding": "🧮",
            "storing": "💾",
            "indexing": "🔍",
            "complete": "🎉",
            "error": "❌"
        }
        emoji = stage_emoji.get(progress.stage, "⏳")
        
        if progress.stage == "error":
            print_error(f"{progress.message}")
        else:
            print(f"{emoji} [{progress.stage.upper()}] %{progress.progress:.1f} - {progress.message}")
            if progress.current_step > 0:
                print(f"   Step {progress.current_step}/{progress.total_steps}")
    
    # Pipeline'a callback ekle
    ingestion_pipeline.set_progress_callback(progress_callback)
    
    print_header("INGESTION BAŞLIYOR")
    
    start_time = datetime.now()
    
    # Ingestion çalıştır
    try:
        result = ingestion_pipeline.ingest_pdf(
            file_data=pdf_data,
            filename=pdf_path.name,
            metadata={
                "category": "tüzük",
                "tags": ["harcırah", "resmi", "posta"],
                "language": "tr",
                "source": "test_script",
                "ingestion_date": datetime.now().isoformat()
            },
            chunk_strategy="token",
            chunk_size=512,
            chunk_overlap=50
        )
    except Exception as e:
        print_error(f"Ingestion hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    
    # Sonuçları göster
    print_header("SONUÇLAR")
    
    if result["status"] == "success":
        print_success("Ingestion başarılı!")
        print()
        
        # Temel bilgiler
        print(f"{Colors.BOLD}📑 Document ID:{Colors.ENDC} {result['document_id']}")
        print(f"{Colors.BOLD}⏱️  İşlem Süresi:{Colors.ENDC} {result['processing_time']:.2f} saniye")
        print(f"{Colors.BOLD}⏱️  Toplam Süre:{Colors.ENDC} {total_time:.2f} saniye")
        
        # İstatistikler
        print(f"\n{Colors.BOLD}📊 İSTATİSTİKLER:{Colors.ENDC}")
        stats = result['stats']
        print(f"  • Sayfa Sayısı: {stats['pages_processed']}")
        print(f"  • Oluşturulan Chunk: {stats['chunks_created']}")
        print(f"  • Kaydedilen Chunk: {stats['chunks_saved']}")
        print(f"  • İndekslenen Chunk: {stats['chunks_indexed']}")
        print(f"  • Toplam Token: {stats['total_tokens']:,}")
        print(f"  • Ortalama Chunk Boyutu: {stats['avg_chunk_size']:.1f} token")
        
        # Doküman metadata
        print(f"\n{Colors.BOLD}📄 DOKÜMAN BİLGİLERİ:{Colors.ENDC}")
        doc_meta = result['document_metadata']
        for key, value in doc_meta.items():
            if value:
                if key == "file_size":
                    print(f"  • {key}: {value:,} bytes")
                else:
                    print(f"  • {key}: {value}")
        
        # Chunk stratejisi
        print(f"\n{Colors.BOLD}⚙️  CHUNK STRATEJİSİ:{Colors.ENDC}")
        print(f"  • Strateji: {result['chunk_strategy']}")
        print(f"  • Chunk Boyutu: {result['chunk_size']} token")
        print(f"  • Overlap: {result['chunk_overlap']} token")
        
        # Performans metrikleri
        if stats['chunks_created'] > 0:
            print(f"\n{Colors.BOLD}📈 PERFORMANS:{Colors.ENDC}")
            chunks_per_page = stats['chunks_created'] / stats['pages_processed']
            tokens_per_page = stats['total_tokens'] / stats['pages_processed']
            processing_speed = stats['total_tokens'] / result['processing_time']
            
            print(f"  • Sayfa başına chunk: {chunks_per_page:.1f}")
            print(f"  • Sayfa başına token: {tokens_per_page:.1f}")
            print(f"  • İşleme hızı: {processing_speed:.1f} token/saniye")
        
        # Sonucu JSON olarak kaydet
        output_file = f"ingestion_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print_success(f"\nSonuçlar kaydedildi: {output_file}")
        
    else:
        print_error(f"Ingestion başarısız: {result.get('error', 'Bilinmeyen hata')}")
        if 'processing_time' in result:
            print_info(f"İşlem süresi: {result['processing_time']:.2f} saniye")
    
    return result

async def main():
    """Main test function"""
    try:
        # Ingestion testi
        result = await test_pdf_ingestion()
        
        if result and result["status"] == "success":
            print_header("TEST BAŞARILI")
            print_success("Tüm aşamalar başarıyla tamamlandı!")
            
            # Özet
            print(f"\n{Colors.BOLD}📝 ÖZET:{Colors.ENDC}")
            print(f"  • 1 PDF → {result['stats']['pages_processed']} sayfa")
            print(f"  • {result['stats']['pages_processed']} sayfa → {result['stats']['chunks_created']} chunk")
            print(f"  • {result['stats']['chunks_created']} chunk → {result['stats']['chunks_indexed']} vektör")
            print(f"  • Toplam: {result['stats']['total_tokens']:,} token işlendi")
        else:
            print_header("TEST BAŞARISIZ")
            print_error("Test tamamlanamadı!")
            
    except Exception as e:
        print_error(f"Test hatası: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           OneDocs RAG Pipeline Test Suite               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    
    asyncio.run(main())