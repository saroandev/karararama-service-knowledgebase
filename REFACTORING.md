# 📦 RAG Project Refactoring Plan

## 🎯 Hedef
App klasörünü modüler package yapısına dönüştürmek ve kodu daha tutarlı, test edilebilir ve sürdürülebilir hale getirmek.

## 📊 İlerleme Durumu
- [x] **Aşama 1**: Config Package ✅ (Tamamlandı - 2025-09-17)
- [ ] **Aşama 2**: Core Packages
- [ ] **Aşama 3**: Pipelines Package
- [ ] **Aşama 4**: Utilities Package
- [ ] **Aşama 5**: Cleanup & Documentation

---

## 📋 Detaylı Plan

### Aşama 1: Config Package Oluşturma ✅

#### Yapılacaklar:
- [x] `app/config/` klasörünü oluştur ✅
- [x] `app/config/__init__.py` dosyasını oluştur ✅
- [x] `app/config.py` → `app/config/settings.py` olarak taşı ✅
- [x] `app/config/validators.py` dosyasını oluştur (config validation için) ✅
- [x] `app/config/constants.py` dosyasını oluştur (sabit değerler için) ✅
- [x] Tüm `from app.config import settings` import'larını test et ✅
- [x] API endpoint'lerinin çalıştığını doğrula ✅
- [ ] Unit test'leri güncelle (ileride yapılacak)

#### Test Checklist:
- [x] `python -m api.main` çalışıyor mu? ✅
- [x] Health endpoint: `curl http://localhost:8080/health` ✅
- [x] Mevcut import'lar çalışıyor mu? ✅
- [x] Backward compatibility korundu mu? ✅

#### Tamamlanan Dosyalar:
1. `app/config/settings.py` - Ana settings class'ı
2. `app/config/__init__.py` - Backward compatibility wrapper
3. `app/config/validators.py` - Config validation fonksiyonları
4. `app/config/constants.py` - Sabit değerler
5. `app/config.py` - Backward compatibility için wrapper (deprecated)

---

### Aşama 2: Core Packages Oluşturma 🔄

#### 2.1 Embeddings Package ✅
- [x] `app/core/embeddings/` klasörünü oluştur ✅
- [x] `app/core/embeddings/__init__.py` ✅
- [x] `app/core/embeddings/base.py` (AbstractEmbedding class) ✅
- [x] `app/core/embeddings/openai_embeddings.py` ✅
- [x] `app/core/embeddings/local_embeddings.py` ✅
- [x] `app/embed.py` içeriğini migrate et ✅
- [x] Backward compatibility için wrapper ekle ✅
- [ ] Test coverage ekle (ileride yapılacak)

#### 2.2 Generation Package ✅
- [x] `app/core/generation/` klasörünü oluştur ✅
- [x] `app/core/generation/__init__.py` ✅
- [x] `app/core/generation/base.py` (AbstractGenerator class) ✅
- [x] `app/core/generation/openai_generator.py` ✅
- [x] `app/core/generation/ollama_generator.py` ✅
- [x] `app/generate.py` içeriğini migrate et ✅
- [x] Backward compatibility için wrapper ekle ✅
- [ ] Test coverage ekle (ileride yapılacak)

#### 2.3 Parsing Package ✅
- [x] `app/core/parsing/` klasörünü oluştur ✅
- [x] `app/core/parsing/__init__.py` ✅
- [x] `app/core/parsing/base.py` (AbstractParser class) ✅
- [x] `app/core/parsing/pdf_parser.py` ✅
- [x] `app/core/parsing/utils.py` ✅
- [x] `app/parse.py` içeriğini migrate et ✅
- [x] Backward compatibility için wrapper ekle ✅
- [ ] Test coverage ekle (ileride yapılacak)

#### 2.4 Indexing Package ✅
- [x] `app/core/indexing/` klasörünü oluştur ✅
- [x] `app/core/indexing/__init__.py` ✅
- [x] `app/core/indexing/base.py` (AbstractIndexer class) ✅
- [x] `app/core/indexing/milvus_indexer.py` ✅
- [x] `app/core/indexing/utils.py` ✅
- [x] `app/index.py` içeriğini migrate et ✅
- [x] Backward compatibility için wrapper ekle ✅
- [ ] Test coverage ekle (ileride yapılacak)

#### 2.5 Retrieval Package ✅
- [x] `app/core/retrieval/` klasörünü oluştur ✅
- [x] `app/core/retrieval/__init__.py` ✅
- [x] `app/core/retrieval/base.py` (AbstractRetriever class) ✅
- [x] `app/core/retrieval/vector_search.py` ✅
- [x] `app/core/retrieval/reranker.py` ✅
- [x] `app/core/retrieval/hybrid_retriever.py` ✅
- [x] `app/core/retrieval/utils.py` ✅
- [x] `app/retrieve.py` içeriğini migrate et ✅
- [x] Backward compatibility için wrapper ekle ✅
- [ ] Test coverage ekle (ileride yapılacak)

---

### Aşama 3: Pipelines Package Oluşturma 🔀

- [ ] `app/pipelines/` klasörünü oluştur
- [ ] `app/pipelines/__init__.py`
- [ ] `app/pipelines/base.py` (AbstractPipeline class)
- [ ] `app/pipelines/ingest_pipeline.py`
- [ ] `app/pipelines/query_pipeline.py`
- [ ] `app/pipelines/utils.py`
- [ ] `app/ingest.py` içeriğini refactor et
- [ ] Pipeline orchestration logic ekle
- [ ] Error handling ve retry logic ekle
- [ ] Test coverage ekle

---

### Aşama 4: Utilities Package Oluşturma 🛠️

- [ ] `app/utils/` klasörünü oluştur
- [ ] `app/utils/__init__.py`
- [ ] `app/utils/logging.py` (centralized logging)
- [ ] `app/utils/decorators.py` (retry, cache, etc.)
- [ ] `app/utils/validators.py` (input validation)
- [ ] `app/utils/helpers.py` (utility functions)
- [ ] Mevcut utility fonksiyonlarını taşı
- [ ] Test coverage ekle

---

### Aşama 5: Cleanup & Documentation 🧹

- [ ] Eski dosyaları `app/legacy/` klasörüne taşı
- [ ] Deprecation warning'leri ekle
- [ ] `app/__init__.py` dosyasını güncelle (main exports)
- [ ] README.md'yi güncelle
- [ ] CLAUDE.md'yi güncelle
- [ ] API dokümantasyonunu güncelle
- [ ] Migration guide yaz
- [ ] Performance test'leri çalıştır
- [ ] Integration test'leri güncelle

---

## 🏗️ Yeni Klasör Yapısı

```
app/
├── __init__.py            # Main exports & backward compatibility
├── config/                # Configuration package
│   ├── __init__.py
│   ├── settings.py        # Settings class
│   ├── validators.py      # Config validation
│   └── constants.py       # Constants
│
├── core/                  # Core business logic
│   ├── __init__.py
│   ├── embeddings/        # Embedding services
│   ├── generation/        # LLM generation
│   ├── parsing/           # Document parsing
│   ├── indexing/          # Vector indexing
│   └── retrieval/         # Search & retrieval
│
├── pipelines/             # Processing pipelines
│   ├── __init__.py
│   ├── base.py
│   ├── ingest_pipeline.py
│   └── query_pipeline.py
│
├── chunking/              # ✅ Already modular
├── storage/               # ✅ Already modular
│
├── utils/                 # Utility functions
│   ├── __init__.py
│   ├── logging.py
│   ├── decorators.py
│   └── helpers.py
│
└── legacy/                # Old files (to be removed later)
    ├── embed.py
    ├── generate.py
    ├── parse.py
    ├── index.py
    ├── retrieve.py
    └── ingest.py
```

---

## 📝 Notlar

### Backward Compatibility Strategy
```python
# app/__init__.py örneği
from app.core.parsing import PDFParser
from app.config import settings

# Eski import'ları destekle
def parse_pdf(file_path):
    """Deprecated: Use app.core.parsing.PDFParser instead"""
    import warnings
    warnings.warn(
        "parse_pdf is deprecated, use PDFParser from app.core.parsing",
        DeprecationWarning,
        stacklevel=2
    )
    parser = PDFParser()
    return parser.parse(file_path)
```

### Testing Strategy
1. Her package için ayrı test modülü
2. Unit test coverage > %80
3. Integration test'ler için ayrı suite
4. Performance benchmark'lar

### Migration Rules
1. ✅ Her zaman backward compatibility koru
2. ✅ Önce yeni yapıyı oluştur, sonra eski kodu taşı
3. ✅ Her adımda test et
4. ✅ Dokümantasyonu güncelle
5. ✅ Commit'leri atomik tut

---

## 📈 İlerleme Metrikleri

| Metrik | Başlangıç | Hedef | Mevcut |
|--------|-----------|--------|---------|
| Package Sayısı | 2 | 8 | 4 |
| Test Coverage | ~%60 | >%80 | ~%60 |
| Code Duplication | Yüksek | Düşük | Orta |
| Modülerlik Skoru | 3/10 | 9/10 | 5/10 |
| Dokümantasyon | %40 | %100 | %50 |

---

## 🚀 Durum

**Tamamlanan**:
- Aşama 1 - Config package ✅
- Aşama 2.1 - Embeddings package ✅
- Aşama 2.2 - Generation package ✅
- Aşama 2.3 - Parsing package ✅
- Aşama 2.4 - Indexing package ✅
- Aşama 2.5 - Retrieval package ✅

Config, Embeddings, Generation, Parsing, Indexing ve Retrieval package'ları başarıyla oluşturuldu. Sistem backward compatibility ile çalışmaya devam ediyor. Tüm retrieval stratejileri (vector search, reranking, MMR, hybrid) yeni modüler yapıya taşındı.

**Sonraki Adım**: Aşama 3 - Pipelines Package

---

*Son Güncelleme: 2025-09-17*
*Durum: Aşama 2.5 Tamamlandı*