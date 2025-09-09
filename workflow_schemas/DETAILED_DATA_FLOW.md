# 📊 RAG Pipeline Detaylı Veri Akışı

Bu dokümantasyon, her komponentin tam olarak ne aldığını ve ne döndürdüğünü gösterir.

## 🔄 Pipeline Özeti

```
PDF Bytes → Parse → Pages → Chunk → Chunks → Embed → Vectors → Index → Milvus
```

## 📝 Detaylı Component Input/Output Analizi

### 1️⃣ **PDF Upload (İlk Giriş)**

**INPUT:**
```python
{
    "file_data": bytes,        # PDF dosyasının binary içeriği
    "filename": str,           # "document.pdf"
    "metadata": Dict[str, Any] # {"category": "teknik", "tags": ["önemli"]}
}
```

**PROCESS:**
- `storage.upload_pdf()` çağrılır
- PDF MinIO'ya yüklenir

**OUTPUT:**
```python
document_id: str  # "doc_20240104_123456_a1b2c3"
```

---

### 2️⃣ **PDF Parsing (Text Extraction)**

**INPUT:**
```python
file_data: bytes  # Aynı PDF binary data
```

**PROCESS:**
- `pdf_parser.extract_text_from_pdf()` çağrılır
- PyMuPDF kullanarak her sayfa işlenir

**OUTPUT:**
```python
(
    pages: List[PageContent],     # Sayfa listesi
    doc_metadata: DocumentMetadata # Doküman meta bilgisi
)

# PageContent yapısı:
PageContent {
    page_number: int,      # 1, 2, 3...
    text: str,            # "Bu sayfanın tüm metni..."
    metadata: {
        "page_number": 1,
        "width": 595.0,
        "height": 842.0,
        "rotation": 0,
        "has_images": True,
        "has_links": False,
        "char_count": 2456,
        "word_count": 412,
        "has_tables": False
    }
}

# DocumentMetadata yapısı:
DocumentMetadata {
    title: "Doküman Başlığı",
    author: "Yazar Adı",
    subject: "Konu",
    page_count: 25,
    file_size: 1048576,  # bytes
    document_hash: "abc123def456",
    creation_date: "2024-01-01"
}
```

**ÖNEMLİ:** 
- Birden fazla sayfa döner (List)
- Boş sayfalar atlanır
- Her sayfanın kendi metadatası var

---

### 3️⃣ **Text Chunking (Parçalama)**

**INPUT:**
```python
{
    "pages": List[PageContent],     # Parse'dan gelen sayfalar
    "document_id": str,              # "doc_20240104_123456_a1b2c3"
    "chunk_strategy": str,           # "token" | "semantic" | "hybrid"
    "chunk_size": int,               # 512
    "chunk_overlap": int             # 50
}
```

**PROCESS:**
```python
# Eğer chunk_strategy == "hybrid":
text = "\\n\\n".join(page.text for page in pages)  # Tüm sayfaları birleştir
chunks = HybridChunker.chunk_text(text)

# Eğer chunk_strategy == "token":
chunks = TextChunker.chunk_pages(pages, preserve_pages=True)
```

**OUTPUT:**
```python
chunks: List[Chunk]  # Chunk listesi

# Her Chunk yapısı:
Chunk {
    chunk_id: "chunk_doc_20240104_123456_a1b2c3_0001_f47ac10b",
    document_id: "doc_20240104_123456_a1b2c3",
    chunk_index: 0,        # 0, 1, 2, 3...
    text: "Bu chunk'ın metni, yaklaşık 512 token...",
    metadata: {
        "document_id": "doc_20240104_123456_a1b2c3",
        "chunk_index": 0,
        "chunk_method": "token",
        "chunk_size_target": 512,
        "chunk_overlap": 50,
        "page_number": 1,      # Hangi sayfadan geldiği
        "category": "teknik",  # Orijinal metadata
        "tags": ["önemli"]
    },
    token_count: 498,
    char_count: 2834
}
```

**ÖNEMLİ:**
- 1 PDF → N sayfa → M chunk (M >> N)
- Örnek: 25 sayfalık PDF → 150-200 chunk olabilir
- Her chunk benzersiz ID alır
- Chunk'lar sıralı (chunk_index)

---

### 4️⃣ **Embedding Generation (Vektör Üretimi)**

**INPUT:**
```python
chunk_texts: List[str]  # ["chunk1 metni", "chunk2 metni", ...]
# Sadece chunk'ların text kısımları
```

**PROCESS:**
- `embedding_generator.generate_embeddings_batch()` çağrılır
- OpenAI veya local model kullanılır

**OUTPUT:**
```python
embeddings: List[List[float]]  # Vektör listesi

# Her embedding:
[
    [0.0234, -0.0567, 0.0891, ...],  # 1536 boyutlu vektör (OpenAI)
    [0.0123, -0.0456, 0.0789, ...],  # chunk_1 için
    [0.0345, -0.0678, 0.0912, ...],  # chunk_2 için
    ...
]
```

**ÖNEMLİ:**
- chunks listesi ile aynı sırada
- Her chunk için 1 vektör
- Boyut: OpenAI=1536, Local=384-768

---

### 5️⃣ **Storage Save (MinIO Depolama)**

**INPUT:**
```python
{
    "document_id": str,
    "chunk_data_list": List[Dict]  # Chunk'ların dict versiyonu
}

# Her chunk_dict:
{
    "chunk_id": "chunk_doc_20240104_123456_a1b2c3_0001_f47ac10b",
    "text": "Chunk metni...",
    "metadata": {...},
    "token_count": 498,
    "char_count": 2834
}
```

**PROCESS:**
- `storage.save_chunks_batch()` çağrılır
- Her chunk JSON olarak MinIO'ya yazılır

**OUTPUT:**
```python
saved_count: int  # Kaydedilen chunk sayısı (150)
```

---

### 6️⃣ **Vector Indexing (Milvus İndeksleme)**

**INPUT:**
```python
{
    "milvus_chunks": List[Dict],     # Chunk bilgileri
    "embeddings": List[List[float]]  # Vektörler
}

# milvus_chunks ve embeddings aynı sırada ve sayıda!
```

**PROCESS:**
- `milvus_indexer.insert_chunks()` çağrılır
- Her chunk + vektör Milvus'a eklenir

**OUTPUT:**
```python
indexed_count: int  # İndekslenen chunk sayısı (150)
```

---

## 📊 Örnek Senaryo: 10 Sayfalık PDF

```python
# 1. INPUT: 1.2 MB PDF dosyası
file_data = b"..." # 1,258,291 bytes

# 2. PARSE OUTPUT: 10 sayfa
pages = [
    PageContent(page_number=1, text="Sayfa 1 metni..." ),
    PageContent(page_number=2, text="Sayfa 2 metni..." ),
    # ... 10 sayfa
]

# 3. CHUNK OUTPUT: 45 chunk (her sayfa ~4-5 chunk)
chunks = [
    Chunk(chunk_id="chunk_doc_123_0000_abc", text="İlk 512 token..."),
    Chunk(chunk_id="chunk_doc_123_0001_def", text="İkinci 512 token..."),
    # ... 45 chunk
]

# 4. EMBEDDING OUTPUT: 45 vektör
embeddings = [
    [0.023, -0.045, ...],  # 1536 boyutlu
    [0.034, -0.056, ...],
    # ... 45 vektör
]

# 5. STORAGE OUTPUT
saved_count = 45  # Tüm chunk'lar MinIO'da

# 6. INDEX OUTPUT
indexed_count = 45  # Tüm vektörler Milvus'ta
```

---

## 🔍 Final Result (Son Çıktı)

```python
{
    "status": "success",
    "document_id": "doc_20240104_123456_a1b2c3",
    "processing_time": 12.5,  # saniye
    "stats": {
        "pages_processed": 10,
        "chunks_created": 45,
        "chunks_saved": 45,
        "chunks_indexed": 45,
        "total_tokens": 22500,  # 45 * ~500
        "avg_chunk_size": 500
    },
    "document_metadata": {
        "title": "Örnek Doküman",
        "author": "Yazar",
        "page_count": 10,
        "file_size": 1258291
    }
}
```

---

## 🗂️ Veri Depolama Yerleri

### MinIO'da:
```
/raw-pdfs/
  └── doc_20240104_123456_a1b2c3.pdf  # Orijinal PDF

/chunks/
  └── doc_20240104_123456_a1b2c3/
      ├── chunk_0000.json
      ├── chunk_0001.json
      └── ... (45 dosya)
```

### Milvus'ta:
```sql
Collection: rag_chunks
Fields:
  - chunk_id (primary key)
  - document_id
  - chunk_index
  - text
  - embedding (vector, dim=1536)
  - metadata (JSON)

Rows: 45 (bu doküman için)
```

---

## ⚠️ Önemli Notlar

1. **Çoklu PDF Desteği:** Sistem aynı anda birden fazla PDF işleyebilir
2. **Chunk Sayısı:** Chunk sayısı = (toplam_token / chunk_size) * (1 + overlap_factor)
3. **Bellek Kullanımı:** 45 chunk * 1536 float * 4 byte = ~276 KB sadece vektörler için
4. **Hata Durumu:** Herhangi bir aşamada hata olursa, tüm işlem geri alınır (cleanup)
5. **Performans:** 10 sayfalık PDF ~10-15 saniyede işlenir

---

## 🔄 Query Time Data Flow (Sorgulama Zamanı)

Query zamanında ters yönde çalışır:

```
Question → Embed → Vector → Milvus Search → Chunks → Generate → Answer
```

1. Soru vektöre çevrilir (1536 boyut)
2. Milvus'ta benzer vektörler aranır
3. En yakın chunk'lar getirilir
4. Chunk metinleri context olarak LLM'e gönderilir
5. LLM cevap üretir