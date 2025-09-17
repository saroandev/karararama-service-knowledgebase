# Schema Reorganizasyon Planı

## Mevcut Durum Analizi

### Şu Anki Yapı
- **schemas/** klasörü zaten var ve kısmen organize edilmiş durumda
- Mevcut alt klasörler:
  - `entities/`
  - `internal/`
  - `parsing/`
  - `requests/`
  - `responses/`
- **app/core/** altında birçok modül mevcut:
  - `chunking/`
  - `embeddings/`
  - `generation/`
  - `indexing/`
  - `parsing/`
  - `retrieval/`
  - `storage/`
- **app/config/** altında Settings sınıfı mevcut (Pydantic model değil, plain class)

### Mevcut Schema Dosyaları
```
schemas/
├── __init__.py (merkezi export noktası)
├── entities/
│   └── __init__.py
├── internal/
│   ├── __init__.py
│   └── chunk.py (SimpleChunk, ChunkMetadata)
├── parsing/
│   ├── __init__.py
│   ├── document.py (DocumentMetadata, DocumentProcessingResult)
│   └── page.py (PageContent)
├── requests/
│   ├── __init__.py
│   ├── ingest.py (IngestRequest)
│   └── query.py (QueryRequest)
└── responses/
    ├── __init__.py
    ├── document.py (DocumentInfo)
    ├── health.py (HealthResponse, ServiceStatus)
    ├── ingest.py (BaseIngestResponse, SuccessfulIngestResponse, vb.)
    └── query.py (QueryResponse, QuerySource)
```

## Hedef Schema Yapısı

```
schemas/
├── __init__.py (merkezi export noktası)
├── api/
│   ├── __init__.py
│   ├── requests/  (mevcut requests klasörü buraya taşınacak)
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   └── query.py
│   └── responses/ (mevcut responses klasörü buraya taşınacak)
│       ├── __init__.py
│       ├── document.py
│       ├── health.py
│       ├── ingest.py
│       └── query.py
├── chunking/
│   ├── __init__.py
│   ├── base.py (Chunk, ChunkingMethod dataclass'ları)
│   ├── text.py (TextChunkConfig, TextChunkResult)
│   ├── semantic.py (SemanticChunkConfig, SemanticChunkResult)
│   ├── document.py (DocumentChunkConfig)
│   └── hybrid.py (HybridChunkConfig)
├── embeddings/
│   ├── __init__.py
│   ├── base.py (EmbeddingConfig, EmbeddingResult)
│   ├── openai.py (OpenAIEmbeddingConfig)
│   └── local.py (LocalEmbeddingConfig)
├── storage/
│   ├── __init__.py
│   ├── minio.py (MinIOConfig, DocumentStorage, ChunkStorage)
│   ├── milvus.py (MilvusConfig, CollectionSchema, IndexConfig)
│   └── cache.py (CacheConfig, CacheEntry)
├── retrieval/
│   ├── __init__.py
│   ├── search.py (SearchQuery, SearchResult, SearchFilter)
│   ├── reranker.py (RerankerConfig, RerankedResult)
│   └── hybrid.py (HybridSearchConfig)
├── generation/
│   ├── __init__.py
│   ├── llm.py (LLMConfig, GenerationRequest, GenerationResponse)
│   └── prompt.py (PromptTemplate, PromptConfig)
├── config/
│   ├── __init__.py
│   ├── app.py (ApplicationConfig - Settings sınıfını Pydantic'e dönüştür)
│   ├── milvus.py (MilvusSettings)
│   ├── minio.py (MinIOSettings)
│   └── llm.py (LLMSettings)
├── parsing/ (mevcut - korunacak ve genişletilecek)
│   ├── __init__.py
│   ├── document.py
│   └── page.py
├── internal/ (mevcut - korunacak)
│   ├── __init__.py
│   └── chunk.py
├── entities/ (mevcut - korunacak ve genişletilecek)
│   └── __init__.py
├── pipelines/
│   ├── __init__.py
│   ├── ingest.py (IngestPipelineConfig, IngestPipelineResult)
│   └── query.py (QueryPipelineConfig, QueryPipelineResult)
└── indexing/
    ├── __init__.py
    └── milvus.py (IndexConfig, IndexingResult)
```

## Göçüş Adımları

### Adım 1: Yeni Klasör Yapısını Oluştur ✅
- [x] `schemas/api/` klasörünü oluştur
- [x] `schemas/chunking/` klasörünü oluştur
- [x] `schemas/embeddings/` klasörünü oluştur
- [x] `schemas/storage/` klasörünü oluştur
- [x] `schemas/retrieval/` klasörünü oluştur
- [x] `schemas/generation/` klasörünü oluştur
- [x] `schemas/config/` klasörünü oluştur
- [x] `schemas/pipelines/` klasörünü oluştur
- [x] `schemas/indexing/` klasörünü oluştur
- [x] Her klasöre `__init__.py` dosyası ekle

### Adım 2: API Schemas'ını Taşı ✅
- [x] `schemas/requests/` klasörünü `schemas/api/requests/` olarak taşı
- [x] `schemas/responses/` klasörünü `schemas/api/responses/` olarak taşı
- [x] API endpoints'teki import'ları güncelle
  - [x] `api/endpoints/ingest.py`
  - [x] `api/endpoints/query.py`
  - [x] `api/endpoints/health.py`
  - [x] `api/endpoints/documents.py`
- [x] `schemas/__init__.py` dosyasındaki export'ları güncelle
- [x] API'nin çalıştığını test et

### Adım 3: Config Schemas'ını Oluştur ✅
- [x] `app/config/settings.py`'deki Settings sınıfını Pydantic BaseModel'e dönüştür
- [x] `schemas/config/app.py` oluştur (ApplicationConfig)
- [x] `schemas/config/milvus.py` oluştur (MilvusSettings)
- [x] `schemas/config/minio.py` oluştur (MinIOSettings)
- [x] `schemas/config/llm.py` oluştur (LLMSettings)
- [x] `schemas/config/__init__.py` ile helper fonksiyonlar eklendi
- [x] Test script ile tüm config'ler doğrulandı

### Adım 4: Chunking Schemas'ını Oluştur ✅
- [x] `app/core/chunking/base.py`'deki dataclass'ları Pydantic model olarak `schemas/chunking/base.py`'ye taşı
- [x] `schemas/chunking/text.py` oluştur
- [x] `schemas/chunking/semantic.py` oluştur
- [x] `schemas/chunking/document.py` oluştur
- [x] `schemas/chunking/hybrid.py` oluştur
- [x] `schemas/chunking/__init__.py` ile exports ve helper fonksiyonlar eklendi

### Adım 5: Storage Schemas'ını Oluştur
- [ ] `schemas/storage/minio.py` oluştur
- [ ] `schemas/storage/milvus.py` oluştur
- [ ] `schemas/storage/cache.py` oluştur
- [ ] Storage modüllerindeki import'ları güncelle

### Adım 6: Embeddings Schemas'ını Oluştur
- [ ] `schemas/embeddings/base.py` oluştur
- [ ] `schemas/embeddings/openai.py` oluştur
- [ ] `schemas/embeddings/local.py` oluştur
- [ ] Embeddings modüllerindeki import'ları güncelle

### Adım 7: Retrieval Schemas'ını Oluştur
- [ ] `schemas/retrieval/search.py` oluştur
- [ ] `schemas/retrieval/reranker.py` oluştur
- [ ] `schemas/retrieval/hybrid.py` oluştur
- [ ] Retrieval modüllerindeki import'ları güncelle

### Adım 8: Generation Schemas'ını Oluştur
- [ ] `schemas/generation/llm.py` oluştur
- [ ] `schemas/generation/prompt.py` oluştur
- [ ] Generation modüllerindeki import'ları güncelle

### Adım 9: Pipeline Schemas'ını Oluştur
- [ ] `schemas/pipelines/ingest.py` oluştur
- [ ] `schemas/pipelines/query.py` oluştur
- [ ] Pipeline modüllerindeki import'ları güncelle

### Adım 10: Indexing Schemas'ını Oluştur
- [ ] `schemas/indexing/milvus.py` oluştur
- [ ] Indexing modüllerindeki import'ları güncelle

### Adım 11: Ana __init__.py Dosyasını Güncelle
- [ ] `schemas/__init__.py`'yi yeni yapıya göre düzenle
- [ ] Tüm export'ları güncelle

### Adım 12: Test ve Doğrulama
- [ ] API'nin çalıştığını doğrula (`python -m api.main`)
- [ ] Tüm endpoint'leri test et
- [ ] Import hatalarını kontrol et
- [ ] Type checking çalıştır (mypy varsa)

## Notlar

### Dikkat Edilecek Noktalar
1. **Geriye Uyumluluk**: Mevcut API'lerin çalışmaya devam etmesi kritik
2. **Import Path'leri**: Tüm import'ların doğru güncellenmesi gerekiyor
3. **Pydantic Versiyonu**: Pydantic v2 kullanıldığından emin ol
4. **Test Coverage**: Her değişiklikten sonra test edilmeli

### Faydalar
1. **Modüler Yapı**: Her modül kendi schema'larını yönetiyor
2. **Daha İyi Organizasyon**: İlgili schema'lar bir arada
3. **Kolay Bakım**: Schema'ları bulmak ve güncellemek daha kolay
4. **Type Safety**: Pydantic ile tam tip güvenliği
5. **Validation**: Otomatik veri doğrulama

### Risk Azaltma
1. Her adımdan sonra API'yi test et
2. Git commit'leri ile ilerle
3. Kritik değişiklikleri ayrı branch'te yap
4. Import hatalarını hemen düzelt

## İlerleme Durumu

**Başlangıç Tarihi**: 2025-09-17
**Mevcut Adım**: Adım 5 - Storage Schemas'ını Oluştur
**Son Güncelleme**: 2025-09-17 15:58

### Tamamlanan Adımlar:
- ✅ Adım 1: Yeni klasör yapısı oluşturuldu (api, chunking, embeddings, storage, retrieval, generation, config, pipelines, indexing)
- ✅ Her klasöre __init__.py dosyaları eklendi
- ✅ Adım 2: API Schemas'ını taşıdık
  - requests/ ve responses/ klasörleri api/ altına taşındı
  - Tüm API endpoint import'ları güncellendi
  - schemas/__init__.py export'ları güncellendi
  - API başarıyla başlatıldı ve test edildi
- ✅ Adım 3: Config Schemas'ını oluşturduk
  - ApplicationConfig (ana konfigürasyon)
  - MilvusSettings (vector DB konfigürasyonu)
  - MinIOSettings (object storage konfigürasyonu)
  - LLMSettings (language model konfigürasyonu)
  - Helper fonksiyonlar eklendi
  - Tüm konfigürasyonlar başarıyla test edildi
- ✅ Adım 4: Chunking Schemas'ını oluşturduk
  - Base schemas (Chunk, ChunkMetadata, ChunkingConfig, ChunkingResult)
  - Text chunking schemas (TextChunkConfig, TextChunkResult)
  - Semantic chunking schemas (SemanticChunkConfig, SemanticChunkResult)
  - Document chunking schemas (DocumentChunkConfig, DocumentElement, DocumentStructure)
  - Hybrid chunking schemas (HybridChunkConfig, HybridChunkResult)
  - Helper fonksiyonlar (create_chunk_config, get_default_config)

---

Bu doküman, schema reorganizasyon sürecini takip etmek için kullanılacaktır. Her adım tamamlandıkça işaretlenecek ve notlar eklenecektir.