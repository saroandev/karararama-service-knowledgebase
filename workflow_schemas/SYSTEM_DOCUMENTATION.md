# OneDocs RAG System - Teknik Dokümantasyon

## 📚 Sistem Genel Bakış

Bu dokümantasyon, OneDocs RAG (Retrieval-Augmented Generation) sisteminin tüm bileşenlerini ve çalışma mantığını detaylıca açıklamaktadır.

## 🏗️ Sistem Mimarisi

### Veri Akışı

```
PDF Upload → Parse → Chunk → Embed → Store → Index → Retrieve → Generate → Response
```

### Teknoloji Stack

-   **Storage**: MinIO (S3-uyumlu object storage)
-   **Vector DB**: Milvus (vector similarity search)
-   **Embedding**: Multilingual-E5-small (384 boyut)
-   **Reranker**: BGE-reranker-v2-m3
-   **LLM**: OpenAI GPT-4 veya Ollama (yerel)
-   **API**: FastAPI + WebSocket
-   **Language**: Python 3.x

## 📁 Dosya Yapısı ve Bileşenler

### 1. **config.py** - Sistem Konfigürasyonu

**Önemli Noktalar:**

-   Sistem MinIO (object storage), Milvus (vector database) ve Ollama/OpenAI (LLM) servislerini kullanıyor
-   Multilingual E5 embedding modeli Türkçe dahil çok dilli destek sağlıyor
-   Ortam değişkenleri ile konfigürasyon yönetimi yapılıyor - production'da güvenli deployment sağlıyor

**Konfigürasyon Bileşenleri:**

-   **MinIO** ayarları: Dökümanlar ve chunk'lar için object storage
-   **Milvus** ayarları: Vector database bağlantısı (port 19530)
-   **Model** ayarları: Embedding ve reranker modelleri
-   **LLM** ayarları: Ollama veya OpenAI provider desteği

---

### 2. **parse.py** - PDF Döküman İşleme

**Önemli Noktalar:**

-   PyMuPDF (fitz) kullanılarak PDF'ler bellekte işleniyor - disk I/O'dan kaçınılıyor
-   Her sayfa için zengin metadata çıkarılıyor: tablolar, resimler, linkler, kelime sayısı
-   Layout korunarak metin çıkarma özelliği ile tablo ve yapısal bilgiler korunuyor

**Sınıflar ve Özellikler:**

-   **PageContent**: Her sayfanın metni ve metadata'sı
-   **DocumentMetadata**: Tüm dökümanın metadata'sı (yazar, tarih, hash)
-   **Özellikler**:
    -   Tablo tespiti (`find_tables`)
    -   Resim çıkarma (`extract_images`)
    -   Layout koruma (`extract_text_with_layout`)
    -   Metin temizleme (kontrol karakterleri, fazla boşluklar)

---

### 3. **chunk.py** - Metin Parçalama Stratejileri

**Önemli Noktalar:**

-   4 farklı chunking stratejisi: Token-based, Semantic, Document-based ve Hybrid (Her biri bir class ile temsil ediliyor)
-   SentenceTransformers tokenizer kullanılarak embedding modeli ile uyumlu parçalama
-   Her chunk için MD5 hash ile benzersiz ID oluşturma ve metadata zenginleştirme

**Chunking Stratejileri:**

**TextChunker**: Token/karakter/cümle bazlı parçalama

-   Langchain splitter'ları kullanıyor
-   BGE-M3 tokenizer ile uyumlu
-   Overlap ile context korunuyor

**SemanticChunker**: Anlamsal parçalama

-   Paragraf sınırlarını tespit ediyor
-   Semantik gruplar oluşturuyor
-   Yapısal bütünlüğü koruyor

**DocumentBasedChunker**: Döküman yapısını koruma

-   Sayfa sınırlarını koruyor
-   Büyük sayfaları paragraflarla böler

**HybridChunker**: Otomatik strateji seçimi

-   Metin yapısını analiz eder
-   En uygun chunking metodunu seçer

---

### 4. **embed.py** - Embedding Üretimi

**Önemli Noktalar:**

-   SentenceTransformer ile normalize edilmiş embedding'ler - cosine similarity için optimize
-   CUDA desteği ile GPU'da hızlı embedding üretimi, batch processing ile verimlilik
-   Cache mekanizması ile aynı metinler için tekrar hesaplama yapılmıyor

**Sınıflar:**

**EmbeddingGenerator**: Ana embedding sınıfı

-   SentenceTransformer kullanıyor
-   GPU/CPU otomatik seçimi
-   Batch processing desteği
-   Normalize edilmiş vektörler (cosine similarity için)

**MultilingualEmbedding**: Çok dilli destek

-   BGE-M3 modeli kullanıyor
-   İnstruction prefix desteği (retrieval kalitesini artırır)

**CachedEmbeddingGenerator**: Cache ile optimizasyon

-   Hash tabanlı cache sistemi
-   Batch işlemlerde bile cache kontrolü
-   Tekrar hesaplama maliyetini azaltır

---

### 5. **index.py** - Vector Database İndeksleme

**Önemli Noktalar:**

-   Milvus vector database kullanılarak 384 boyutlu embedding'ler indeksleniyor
-   IVF_FLAT indeks tipi ile Inner Product metriği - normalize vektörler için optimize
-   Batch search desteği ile çoklu sorgu optimizasyonu ve partition desteği

**MilvusIndexer**: Vector database yönetimi

-   **Schema tanımı**: id, embedding, document_id, chunk_id, text, metadata
-   **İndeks tipi**: IVF_FLAT (Inverted File) - orta ölçekli veri için ideal
-   **Metrik**: Inner Product (IP) - normalize vektörler için cosine similarity eşdeğeri

**Özellikler**:

-   Chunk ekleme ve silme
-   Tekli ve batch arama
-   Partition desteği (veri organizasyonu)
-   İndeks yeniden oluşturma
-   Collection istatistikleri

---

### 6. **storage.py** - Object Storage Yönetimi

**Önemli Noktalar:**

-   MinIO object storage ile S3-uyumlu veri saklama - cloud'a kolay geçiş sağlar
-   Hiyerarşik dosya organizasyonu: document_id/filename yapısı
-   Chunk'lar JSON formatında saklanıyor - metadata ile zenginleştirilmiş

**MinIOStorage**: Döküman ve chunk saklama

-   **İki ayrı bucket**:
    -   `rag-docs`: Orijinal PDF'ler
    -   `rag-chunks`: İşlenmiş chunk'lar
-   **Döküman ID oluşturma**: MD5 hash + timestamp
-   **Metadata yönetimi**: Upload zamanı, dosya boyutu, orijinal isim

**Özellikler**:

-   PDF upload/download
-   Chunk kaydetme (JSON formatında)
-   Batch chunk işlemleri
-   Döküman listeleme ve silme
-   Hiyerarşik klasör yapısı

---

### 7. **retrieve.py** - Akıllı Bilgi Getirme

**Önemli Noktalar:**

-   CrossEncoder reranker ile iki aşamalı arama - ilk arama hızlı, reranking daha doğru
-   MMR (Maximal Marginal Relevance) algoritması ile çeşitlilik sağlanıyor
-   Hybrid search: Semantic + keyword arama kombinasyonu daha iyi sonuçlar veriyor

**Retriever**: Çok stratejili arama sistemi

**Temel Arama**:

-   Query embedding oluşturma
-   Milvus'tan vector similarity araması
-   Filter desteği (document_id, page_number)

**Reranking**:

-   CrossEncoder modeli (BGE-reranker-v2-m3)
-   İlk aramada 3x fazla aday çekip rerank ediyor
-   Query-document çiftlerini skorluyor

**Diverse Retrieval (MMR)**:

-   Çeşitlilik için MMR algoritması
-   Hem relevance hem diversity dengesi
-   Tekrarlayan bilgileri önlüyor

**Hybrid Search**:

-   Semantic + keyword kombinasyonu
-   BM25 benzeri keyword skorlama
-   Ağırlıklı skor birleştirme

---

### 8. **generate.py** - LLM ile Yanıt Üretimi

**Önemli Noktalar:**

-   İki provider desteği: OpenAI (GPT-4) ve Ollama (yerel LLM) - maliyet ve gizlilik dengesi
-   Kaynak referanslı yanıtlar - her bilgi için [1], [2] gibi referanslar
-   Streaming desteği ile gerçek zamanlı yanıt üretimi

**LLMGenerator**: Çoklu LLM provider desteği

**Provider Desteği**:

-   **OpenAI**: GPT-4 modeli, streaming desteği
-   **Ollama**: Yerel model (Qwen2.5:7b-instruct), async HTTP

**Yanıt Üretimi**:

-   Context oluşturma (chunk'lardan)
-   Türkçe optimizeli prompt'lar
-   Kaynak referansları ([1], [2] formatında)
-   "Belgelerde yok" durumunu belirtme

**Özellikler**:

-   **Streaming yanıt**: Real-time yanıt üretimi
-   **Kaynak çıkarma**: Regex ile referans bulma
-   **Özet üretme**: Uzun dökümanları özetleme
-   **Token takibi**: Kullanım istatistikleri

---

### 9. **ingest.py** - Ana Veri İşleme Pipeline'ı

**Önemli Noktalar:**

-   6 aşamalı pipeline: Upload → Parse → Chunk → Embed → Store → Index
-   Progress tracking ile gerçek zamanlı ilerleme takibi - callback mekanizması
-   Hata durumunda otomatik cleanup - veritabanı ve storage temizliği

**IngestionPipeline**: End-to-end döküman işleme

**Pipeline Aşamaları**:

1. **Upload** (5%): PDF'i MinIO'ya yükleme
2. **Parsing** (15%): PDF'ten metin çıkarma
3. **Chunking** (30%): Metin parçalama
4. **Embedding** (50%): Vector oluşturma
5. **Storing** (70%): Chunk'ları saklama
6. **Indexing** (85%): Milvus'a ekleme

**Özellikler**:

-   **Progress Tracking**: Callback ile ilerleme bildirimi
-   **Batch İşleme**: Çoklu dosya desteği
-   **Reindexing**: Farklı parametrelerle yeniden işleme
-   **Async Destek**: Non-blocking işlemler
-   **Error Handling**: Hata durumunda cleanup

**Metrikler**:

-   İşleme süresi
-   Sayfa/chunk/token sayıları
-   Ortalama chunk boyutu

---

### 10. **server.py** - REST API ve WebSocket Server

**Önemli Noktalar:**

-   FastAPI ile modern async REST API - WebSocket desteği ile real-time progress
-   Background tasks ile non-blocking dosya işleme - UI donmaları önleniyor
-   Streaming response desteği - LLM yanıtları gerçek zamanlı gösteriliyor

**FastAPI Endpoints**:

### Temel Endpointler:

-   **`GET /health`**: Sistem sağlık kontrolü
-   **`GET /stats`**: Sistem istatistikleri

### Döküman Yönetimi:

-   **`POST /ingest`**: PDF yükleme ve işleme
-   **`GET /documents`**: Döküman listesi (sayfalama)
-   **`GET /documents/{id}`**: Döküman detayları
-   **`DELETE /documents/{id}`**: Döküman silme
-   **`POST /documents/{id}/reindex`**: Yeniden indeksleme
-   **`POST /documents/{id}/summarize`**: Özet oluşturma

### Sorgulama:

-   **`POST /query`**: Soru sorma ve yanıt alma
-   **`POST /query/stream`**: Streaming yanıt

### WebSocket:

-   **`WS /ws`**: Real-time progress güncellemeleri

**Özellikler**:

-   **CORS desteği**: Frontend entegrasyonu
-   **Pydantic modeller**: Type safety
-   **Background tasks**: Async işlemler
-   **WebSocket manager**: Progress broadcasting
-   **Error handling**: Detaylı hata mesajları

---

## 📊 GENEL SİSTEM MİMARİSİ ÖZET

Bu RAG (Retrieval-Augmented Generation) sistemi, PDF dökümanlarından bilgi çıkarıp kullanıcı sorularına yanıt veren gelişmiş bir yapıya sahip.

### Güçlü Yönler:

1. **Modüler Yapı**: Her bileşen bağımsız ve değiştirilebilir
2. **Çok Dilli Destek**: Türkçe dahil birçok dilde çalışıyor
3. **Performans Optimizasyonları**:

    - Cache mekanizmaları
    - Batch processing
    - GPU desteği
    - Async işlemler

4. **Gelişmiş Arama**:

    - Semantic search
    - Reranking
    - MMR diversity
    - Hybrid search

5. **Production Ready**:
    - Error handling
    - Progress tracking
    - WebSocket real-time updates
    - Docker desteği

### Kullanım Senaryoları:

-   Hukuki döküman analizi
-   Teknik dokümantasyon arama
-   Kurumsal bilgi yönetimi
-   Araştırma ve analiz sistemleri

Sistem, hem küçük ölçekli projeler hem de enterprise uygulamalar için uygun bir altyapıya sahip. Mikroservis mimarisi sayesinde kolayca ölçeklenebilir ve özelleştirilebilir.

## 🚀 Çalıştırma

```bash
# Docker servisleri başlat
docker-compose up -d

# Python bağımlılıklarını yükle
pip install -r requirements.txt

# Sunucuyu başlat
python -m uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload
```

## 📝 Notlar

-   Sistem varsayılan olarak localhost üzerinde çalışır
-   MinIO konsolu: http://localhost:9001
-   Milvus: localhost:19530
-   API: http://localhost:8000
-   API Dokümantasyonu: http://localhost:8000/docs
