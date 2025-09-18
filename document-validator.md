# Document Validation Katmanı - Uygulama Planı

## 📋 Genel Bakış

Bu doküman, RAG sistemine eklenecek Document Validation katmanının detaylı uygulama planını içerir. Validation katmanı, mevcut yapıyı bozmadan ara katman olarak çalışacak ve dokümanların doğru şekilde işlenmesini sağlayacaktır.

## 🏗️ Mimari Yapı

### İşlem Akışı
```
ingest_document() endpoint
    ↓
[1] DocumentValidator.validate()  ← YENİ KATMAN
    ├── Hash üretimi (MD5 + SHA256)
    ├── Duplicate kontrolü (Milvus'ta var mı?)
    ├── Doküman tipi tespiti
    ├── Metadata çıkarma
    └── İçerik ön analizi
    ↓
[2] Validation Result
    ├── Eğer EXISTS → Return ExistingDocumentResponse (mevcut yapı)
    └── Eğer NEW → Continue to parsing...
    ↓
[3] PDFParser.extract_text() (mevcut yapı değişmez)
    ↓
[4] Storage & Indexing (mevcut yapı değişmez)
```

## 📁 Klasör Yapısı

### Validation Modülleri
```
app/core/validation/
├── __init__.py               # Ana exports ve konfigürasyon
├── base.py                   # BaseValidator abstract class
├── document_validator.py     # Ana DocumentValidator sınıfı
├── type_detector.py          # Doküman tipi tespiti
├── metadata_extractor.py     # Metadata çıkarma işlemleri
├── content_analyzer.py       # İçerik analizi (tablo, görsel, vb.)
└── utils.py                  # Hash üretimi ve yardımcı fonksiyonlar
```

### Schema Tanımlamaları
```
schemas/validation/
├── __init__.py
├── document_info.py          # DocumentType enum, DocumentInfo model
└── validation_result.py      # ValidationResult, ValidationStatus enum
```

## 🔧 Bileşen Detayları

### 1. DocumentValidator Sınıfı

#### Temel İşlevler
```python
class DocumentValidator:
    async def validate(self, file: UploadFile, milvus_manager) -> ValidationResult:
        """
        Dokümanı validate eder ve işleme hazırlar

        Returns:
            ValidationResult: Validation sonucu ve metadata
        """
        # 1. Dosya okuma
        pdf_data = await file.read()

        # 2. Hash üretimi (mevcut mantık korunur)
        file_hash = hashlib.md5(pdf_data).hexdigest()
        document_id = f"doc_{file_hash[:16]}"

        # 3. Duplicate kontrolü
        existing = self._check_existing_document(document_id, milvus_manager)
        if existing:
            return ValidationResult(
                status=ValidationStatus.EXISTS,
                document_id=document_id,
                existing_metadata=existing['metadata']
            )

        # 4. Doküman tipi tespiti
        document_type = self._detect_type(pdf_data, file.filename)

        # 5. Temel metadata çıkarma
        metadata = self._extract_basic_metadata(pdf_data, file.filename)

        # 6. İçerik ön analizi
        content_info = self._analyze_content(pdf_data)

        return ValidationResult(
            status=ValidationStatus.VALID,
            document_id=document_id,
            document_type=document_type,
            file_hash=file_hash,
            metadata=metadata,
            content_info=content_info,
            pdf_data=pdf_data  # Parsing için saklanır
        )
```

### 2. Type Detector

#### Doküman Tipi Tespiti
- Magic bytes kontrolü
- MIME type tespiti
- Extension kontrolü
- Desteklenen tipler: PDF, DOCX, TXT, HTML

### 3. Metadata Extractor

#### Çıkarılacak Metadata
- **Temel Bilgiler**
  - Dosya adı ve boyutu
  - Oluşturma/değiştirme tarihi
  - Sayfa sayısı (PDF için)

- **PDF Metadata** (PyMuPDF kullanarak)
  - Title, Author, Subject
  - Keywords, Creator, Producer
  - Creation/Modification dates

- **Hesaplanan Bilgiler**
  - MD5 ve SHA256 hash
  - Encoding tespiti
  - Dil tespiti (opsiyonel)

### 4. Content Analyzer

#### İçerik Analizi
- **Yapısal Analiz**
  - Tablo varlığı ve sayısı
  - Görsel/grafik sayısı
  - Bağlantılar (internal/external)

- **Metin Analizi**
  - Toplam kelime sayısı
  - Ortalama sayfa yoğunluğu
  - Metin/görsel oranı

- **Kalite Kontrolleri**
  - Boş sayfa kontrolü
  - OCR gereksinimi tespiti
  - Şifre koruması kontrolü

### 5. ValidationResult Schema

```python
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from datetime import datetime

class ValidationStatus(Enum):
    VALID = "valid"       # Doküman geçerli, işlenebilir
    INVALID = "invalid"   # Doküman geçersiz
    EXISTS = "exists"     # Doküman zaten mevcut

class DocumentType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    UNKNOWN = "unknown"

class ContentInfo(BaseModel):
    has_tables: bool = False
    table_count: int = 0
    has_images: bool = False
    image_count: int = 0
    has_links: bool = False
    link_count: int = 0
    word_count: int = 0
    page_density: float = 0.0  # Kelime/sayfa oranı

class DocumentMetadata(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    page_count: int = 0
    file_size: int = 0
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    language: Optional[str] = None
    encoding: str = "utf-8"

class ValidationResult(BaseModel):
    status: ValidationStatus
    document_id: str
    file_hash: str
    document_type: DocumentType

    # Duplicate durumu için
    existing_metadata: Optional[Dict[str, Any]] = None

    # Yeni doküman için
    metadata: Optional[DocumentMetadata] = None
    content_info: Optional[ContentInfo] = None

    # İşleme devam etmek için
    pdf_data: Optional[bytes] = None

    # İşlem bilgileri
    processing_time: float
    warnings: List[str] = []
    error_message: Optional[str] = None

    # İşleme önerileri
    processing_hints: Dict[str, Any] = {}
```

## 🔄 Entegrasyon

### ingest.py Güncellemesi

```python
from app.core.validation import DocumentValidator
from schemas.validation import ValidationStatus

@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    start_time = datetime.datetime.now()

    try:
        # [YENİ] Validation katmanı
        validator = DocumentValidator()
        validation_result = await validator.validate(file, milvus_manager)

        # Doküman zaten varsa (mevcut ExistingDocumentResponse korunur)
        if validation_result.status == ValidationStatus.EXISTS:
            return ExistingDocumentResponse(
                document_id=validation_result.document_id,
                document_title=validation_result.existing_metadata.get('document_title'),
                processing_time=(datetime.datetime.now() - start_time).total_seconds(),
                file_hash=validation_result.file_hash,
                message="Document already exists in database",
                chunks_count=validation_result.existing_metadata.get('chunks_count', 0)
            )

        # Validation başarısız ise
        if validation_result.status == ValidationStatus.INVALID:
            return FailedIngestResponse(
                document_id="",
                document_title="",
                processing_time=(datetime.datetime.now() - start_time).total_seconds(),
                file_hash="",
                message=f"Validation failed: {validation_result.error_message}",
                error_details=validation_result.error_message
            )

        # [MEVCUT YAPI KORUNUR] Validation başarılı, işleme devam
        document_id = validation_result.document_id
        pdf_data = validation_result.pdf_data

        # MinIO upload (değişmez)
        storage.upload_pdf_to_raw_documents(
            document_id=document_id,
            file_data=pdf_data,
            filename=file.filename,
            metadata={
                "document_id": document_id,
                "file_hash": validation_result.file_hash,
                "original_filename": file.filename,
                "document_type": validation_result.document_type.value,
                "validation_metadata": validation_result.metadata.dict() if validation_result.metadata else {}
            }
        )

        # PDF parsing (değişmez)
        parser = PDFParser()
        pages, metadata = parser.extract_text(pdf_data)

        # Geri kalan işlemler aynı kalır...
        # (chunking, embedding, Milvus insert vb.)

    except Exception as e:
        logger.error(f"Ingest error: {str(e)}")
        # Mevcut error handling...
```

## ✅ Avantajlar

### Mevcut Yapıyı Korur
- Response formatları değişmez
- PDFParser'a dokunulmaz
- Storage işlemleri aynı kalır
- Milvus işlemleri değişmez

### Yeni Yetenekler Ekler
- Merkezi validation mantığı
- Erken duplicate tespiti
- Doküman tipi belirleme
- Genişletilmiş metadata
- İçerik ön analizi
- İşleme önerileri

### Modüler ve Genişletilebilir
- Her validation görevi ayrı modülde
- Yeni doküman tipleri kolayca eklenebilir
- Test edilebilir yapı
- Clean code prensiplerine uygun

## 📝 Uygulama Sırası

1. **Schema Tanımlamaları** (schemas/validation/)
   - ValidationStatus, DocumentType enums
   - ValidationResult model
   - ContentInfo, DocumentMetadata models

2. **Base Validator** (app/core/validation/base.py)
   - Abstract base class
   - Common validation methods

3. **Utility Functions** (app/core/validation/utils.py)
   - Hash generation (MD5, SHA256)
   - File type detection helpers
   - Common validation helpers

4. **Type Detector** (app/core/validation/type_detector.py)
   - Magic bytes checking
   - MIME type detection
   - Extension validation

5. **Metadata Extractor** (app/core/validation/metadata_extractor.py)
   - Basic file metadata
   - PDF-specific metadata (PyMuPDF)
   - Metadata normalization

6. **Content Analyzer** (app/core/validation/content_analyzer.py)
   - Table detection
   - Image/graphic counting
   - Text density calculation

7. **Document Validator** (app/core/validation/document_validator.py)
   - Main orchestrator class
   - Duplicate checking
   - Validation workflow

8. **Ingest Endpoint Entegrasyonu**
   - Import new validator
   - Add validation step
   - Handle validation results

## 🔍 Validation Kontrolleri

### Güvenlik Kontrolleri
- Maksimum dosya boyutu (100MB)
- Maksimum sayfa sayısı (1000)
- Zararlı içerik taraması
- Şifreli PDF kontrolü

### Kalite Kontrolleri
- Minimum içerik kontrolü (100 karakter)
- Boş sayfa oranı kontrolü
- OCR gereksinimi tespiti
- Encoding uyumluluk kontrolü

### Performans Kontrolleri
- Chunk boyutu önerisi
- İşlem stratejisi önerisi
- Bellek kullanımı tahmini

## 📊 Örnek Validation Sonucu

```json
{
  "status": "valid",
  "document_id": "doc_a3f5b2c1d4e6f7g8",
  "file_hash": "a3f5b2c1d4e6f7g8h9i0j1k2l3m4n5o6",
  "document_type": "pdf",
  "metadata": {
    "title": "Türk Ceza Kanunu",
    "author": "T.C. Adalet Bakanlığı",
    "page_count": 156,
    "file_size": 2457600,
    "created_at": "2024-01-15T10:30:00",
    "language": "tr",
    "encoding": "utf-8"
  },
  "content_info": {
    "has_tables": true,
    "table_count": 12,
    "has_images": false,
    "image_count": 0,
    "word_count": 45230,
    "page_density": 290.06
  },
  "processing_time": 0.453,
  "warnings": [],
  "processing_hints": {
    "recommended_chunk_size": 500,
    "use_ocr": false,
    "extract_tables": true,
    "estimated_chunks": 92
  }
}
```

## 🚀 Sonuç

Bu validation katmanı, mevcut RAG sistemine minimum değişiklikle entegre edilecek ve doküman işleme kalitesini artıracaktır. Sistem, her dokümanı işlemeden önce kapsamlı bir validasyondan geçirerek, hatalı veya duplicate işlemleri engelleyecek ve işleme verimliliğini artıracaktır.