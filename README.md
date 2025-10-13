# 🚀 OneDocs Service KnowledgeBase

Enterprise-grade **Multi-tenant RAG (Retrieval-Augmented Generation)** sistemi. Kuruluşların ve kullanıcıların kendi bilgi tabanlarını oluşturmasını, yönetmesini ve akıllı sorgu yapmasını sağlayan production-ready mikroservis.

## 🎯 Ne Yapıyor?

OneDocs KnowledgeBase, kuruluşlar için izole, güvenli ve ölçeklenebilir bir bilgi yönetim platformudur:

- 🏢 **Multi-Tenant Architecture**: Her kuruluş kendi izole ortamında çalışır
- 👥 **Kullanıcı Bazlı Yetkilendirme**: JWT tabanlı authentication ve role-based authorization
- 📚 **Collection Yönetimi**: Kullanıcılar belgelerini koleksiyonlarda organize edebilir
- 🔍 **Çoklu Kaynak Sorgulaması**: Kendi belgeleriniz + harici hukuki veri tabanları (MEVZUAT, KARAR)
- ⚡ **Paralel İşleme**: QueryOrchestrator ile tüm kaynaklar paralel aranır ve sonuçlar birleştirilir
- 🤖 **AI-Powered**: OpenAI GPT-4o-mini ile kaynak göstereli akıllı yanıtlar

## ✨ Temel Özellikler

### 🔐 Güvenlik ve Yetkilendirme
- **JWT Authentication**: OneDocs Auth Service ile entegre
- **Permission-Based Access**: `research:query`, `research:ingest` gibi granular yetkiler
- **Role-Based Control**: Admin ve User rolleri
- **Data Access Flags**: `own_data` ve `shared_data` erişim kontrolü

### 🏗️ Multi-Tenant Data Isolation
- **Organization-Level Isolation**: Her kuruluşun kendi MinIO bucket'ı (`org-{org_id}`)
- **User-Level Privacy**: Private belgelere sadece sahibi erişebilir
- **Shared Workspace**: Organizasyon geneli paylaşılan belgeler
- **Automatic Scoping**: Tüm işlemler otomatik olarak scope'a göre izole edilir

### 📁 Collection Management
- **Named Collections**: Belgelerinizi mantıksal koleksiyonlarda gruplandırın
  - Örnek: "Sözleşmeler", "İç Yönetmelikler", "Müşteri Belgeleri"
- **Scope-Aware Collections**: Her scope'ta (private/shared) ayrı koleksiyonlar
- **CRUD Operations**: Collection oluşturma, listeleme, silme
- **Metadata Tracking**: Her collection için istatistikler (belge sayısı, boyut, vb.)

### 🔄 Orchestrator Pattern
- **IngestOrchestrator**: Belge yükleme pipeline'ı
  - Validation → Parsing → Chunking → Embedding → Indexing → Storage → Usage Tracking
- **QueryOrchestrator**: Çoklu kaynak sorgu koordinasyonu
  - Handler oluşturma → Paralel arama → Sonuç birleştirme → LLM yanıt üretimi

### 🌐 Çoklu Veri Kaynakları
1. **PRIVATE**: Kullanıcının kendi belgeleri
2. **SHARED**: Organizasyonun paylaşılan belgeleri
3. **MEVZUAT**: Türkiye mevzuat veri tabanı (harici servis)
4. **KARAR**: Türkiye içtihat veri tabanı (harici servis)
5. **Collections**: Specific koleksiyonlar içinde arama

## 🛠️ Teknoloji Stack

| Teknoloji | Kullanım Alanı | Versiyon |
|-----------|----------------|----------|
| **FastAPI** | Modern Python web framework | Latest |
| **Milvus** | Vector database (HNSW indexing) | v2.6.1 |
| **MinIO** | S3-compatible object storage | Latest |
| **OpenAI** | Embeddings & LLM | GPT-4o-mini |
| **Docker** | Containerization & orchestration | Latest |
| **PyJWT** | JWT authentication | v2.8.0 |
| **Pydantic** | Data validation | v2.5.0 |

## 🚀 Hızlı Başlangıç

### Gereksinimler
- Docker Desktop (8GB+ RAM)
- Python 3.9+
- OpenAI API Key
- OneDocs Auth Service (JWT token için)

### 1. Repository'yi Klonlayın
```bash
git clone <repository-url>
cd Onedocs-RAG-Project
```

### 2. Environment Variables
`.env` dosyasını oluşturun:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_SECURE=false

# JWT Authentication (CRITICAL - Auth Service ile aynı olmalı)
JWT_SECRET_KEY=dev-secret-key-min-32-characters-long-12345
JWT_ALGORITHM=HS256
REQUIRE_AUTH=true

# Auth Service
AUTH_SERVICE_URL=http://onedocs-auth:8001
AUTH_SERVICE_TIMEOUT=5

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
LOG_LEVEL=INFO
```

### 3. Docker Servislerini Başlatın
```bash
# Tüm servisleri başlat (Milvus, MinIO, ETCD, Attu)
docker compose up -d

# Servis durumlarını kontrol et
docker compose ps

# Logları izle
docker compose logs -f
```

### 4. API Sunucusunu Başlatın
```bash
# Development mode (auto-reload)
make run

# Veya doğrudan uvicorn ile
uvicorn api.main:app --reload --host 0.0.0.0 --port 8080
```

### 5. İlk Test
```bash
# Health check (auth gerektirmez)
curl http://localhost:8080/health

# Auth Service'ten token alın
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Token ile API'ye erişin
export TOKEN="your-jwt-token-here"

curl -X GET http://localhost:8080/collections \
  -H "Authorization: Bearer $TOKEN"
```

## 📡 API Endpoints

### 🔐 Authentication
Tüm endpoint'ler (health hariç) JWT token gerektirir:
```
Authorization: Bearer <your-jwt-token>
```

### 📁 Collection Management

#### 1. Collection Oluştur
```bash
POST /collections
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Sözleşmeler",
  "scope": "private",           # "private" veya "shared"
  "description": "Müşteri sözleşmeleri",
  "metadata": {
    "category": "legal",
    "tags": ["contracts", "customers"]
  }
}
```

**Response:**
```json
{
  "message": "Collection 'Sözleşmeler' created successfully",
  "collection": {
    "name": "Sözleşmeler",
    "scope": "private",
    "document_count": 0,
    "chunk_count": 0,
    "size_mb": 0.0,
    "created_at": "2024-01-15T10:30:00",
    "milvus_collection_name": "user_abc123_col_sozlesmeler_chunks_1536"
  }
}
```

#### 2. Collection Listele
```bash
GET /collections?scope=all        # all, private, veya shared
Authorization: Bearer <token>
```

#### 3. Collection Detayları
```bash
GET /collections/{collection_name}?scope=private
Authorization: Bearer <token>
```

#### 4. Collection Sil
```bash
DELETE /collections/{collection_name}?scope=private
Authorization: Bearer <token>
```
⚠️ **Not**: Shared collection sadece admin silebilir.

#### 5. Collection'daki Belgeleri Listele
```bash
GET /collections/{collection_name}/documents?scope=private
Authorization: Bearer <token>
```

### 📄 Document Ingestion

#### Belge Yükle
```bash
POST /ingest
Content-Type: multipart/form-data
Authorization: Bearer <token>

Form Data:
- file: <pdf-file>
- scope: "private"                  # veya "shared"
- collection_name: "Sözleşmeler"    # opsiyonel (var olan collection)
```

**Response:**
```json
{
  "document_id": "doc_a1b2c3d4e5f6",
  "document_title": "Hizmet Sözleşmesi.pdf",
  "chunks_created": 15,
  "processing_time": 3.45,
  "tokens_used": 1,
  "remaining_credits": 99,
  "scope_info": {
    "scope_type": "private",
    "collection_name": "user_abc123_col_sozlesmeler_chunks_1536",
    "bucket_name": "org-org123"
  },
  "validation_status": "valid",
  "page_count": 8,
  "chunking_stats": {
    "method": "token-based",
    "chunk_size_target": 512,
    "chunk_overlap": 50,
    "avg_tokens_per_chunk": 487
  }
}
```

**Pipeline Stages:**
1. **Validation**: PDF format kontrolü, boyut kontrolü, duplicate detection
2. **Parsing**: PyMuPDF ile text extraction
3. **Chunking**: Token-based chunking (512 token, 50 overlap)
4. **Embedding**: OpenAI text-embedding-3-small (1536 dim)
5. **Indexing**: Milvus HNSW index'e ekleme
6. **Storage**: MinIO'ya PDF ve chunk'ları yükleme
7. **Consume**: Usage tracking ve credit azaltma

### 🔍 Query Processing

#### Akıllı Sorgulama
```bash
POST /chat/process
Content-Type: application/json
Authorization: Bearer <token>

{
  "question": "Hizmet sözleşmelerinde fiyat güncellemesi nasıl yapılır?",
  "sources": ["private", "mevzuat"],     # Opsiyonel: external sources
  "collections": [                        # Collection'ları belirtin
    {
      "name": "Sözleşmeler",
      "scope": "private"
    },
    {
      "name": "İç Yönetmelikler",
      "scope": "shared"
    }
  ],
  "top_k": 5,
  "min_relevance_score": 0.7,
  "options": {
    "tone": "professional",              # casual, professional, academic
    "citations": true,
    "lang": "tur"                        # tur veya eng
  }
}
```

**Response:**
```json
{
  "answer": "Hizmet sözleşmelerinde fiyat güncellemesi...",
  "sources": [
    {
      "text": "İlgili paragraf metni...",
      "score": 0.89,
      "document_id": "doc_abc123",
      "document_title": "Hizmet Sözleşmesi Template.pdf",
      "page_number": 3,
      "chunk_index": 5,
      "source_type": "collection",
      "source_name": "Sözleşmeler (private)"
    },
    {
      "text": "Mevzuat metni...",
      "score": 0.82,
      "source_type": "external",
      "source_name": "MEVZUAT",
      "reference": "6098 Sayılı Borçlar Kanunu, Md. 138"
    }
  ],
  "processing_time": 2.34,
  "model_used": "gpt-4o-mini",
  "tokens_used": 1250,
  "total_sources_retrieved": 12,
  "sources_after_filtering": 7
}
```

**Query Orchestrator İşleyişi:**
1. **Source Expansion**: `sources` ve `collections` parametrelerini analiz et
2. **Handler Creation**: Her kaynak için uygun handler oluştur
   - `CollectionServiceHandler`: Belirtilen collection'larda ara
   - `ExternalServiceHandler`: MEVZUAT ve KARAR servislerinde ara
3. **Parallel Execution**: Tüm handler'lar aynı anda çalışır (asyncio.gather)
4. **Result Aggregation**: `ResultAggregator` sonuçları birleştirir
5. **LLM Generation**: GPT ile kaynak göstereli yanıt üretir

**Önemli Davranışlar:**
- 🚫 **Collections belirtilmezse ve sources sadece external ise**: Sadece external servislerde arama
- 🚫 **Collections belirtilmezse ve sources boş ise**: LLM-only mode (RAG yok)
- ✅ **Collections + external sources**: Her ikisi de paralel aranır ve birleştirilir

### 📋 Document Management

#### Belgeleri Listele
```bash
GET /documents?scope=all&collection=Sözleşmeler
Authorization: Bearer <token>
```

⚠️ **Not**: `collection` parametresi ZORUNLU. Belirtilmezse boş liste döner.

#### Belge Sil
```bash
DELETE /documents/{document_id}?scope=private&collection=Sözleşmeler
Authorization: Bearer <token>
```

## 🏗️ Multi-Tenant Architecture

### Data Isolation Model

```
Organization: org-696e4ef0
├── MinIO Bucket: org-696e4ef0
│   ├── users/
│   │   ├── user-abc123/
│   │   │   ├── docs/               # Default space
│   │   │   ├── chunks/
│   │   │   └── collections/
│   │   │       ├── sozlesmeler/
│   │   │       │   ├── docs/
│   │   │       │   └── chunks/
│   │   │       └── yonetmelikler/
│   │   └── user-xyz789/
│   └── shared/
│       ├── docs/                   # Default shared space
│       ├── chunks/
│       └── collections/
│           └── genel_politikalar/
│
└── Milvus Collections
    ├── user_abc123_chunks_1536                           # User default
    ├── user_abc123_col_sozlesmeler_chunks_1536          # User collection
    ├── org_696e4ef0_shared_chunks_1536                   # Org shared default
    └── org_696e4ef0_col_genel_politikalar_chunks_1536   # Org shared collection
```

### Scope Hierarchy

| Scope | Erişim | Collection Naming | MinIO Path |
|-------|--------|-------------------|------------|
| **PRIVATE** | Sadece owner | `user_{user_id}_chunks_1536` | `users/{user_id}/docs/` |
| **PRIVATE (collection)** | Sadece owner | `user_{user_id}_col_{name}_chunks_1536` | `users/{user_id}/collections/{name}/` |
| **SHARED** | Org members | `org_{org_id}_shared_chunks_1536` | `shared/docs/` |
| **SHARED (collection)** | Org members | `org_{org_id}_col_{name}_chunks_1536` | `shared/collections/{name}/` |

### Permission Matrix

| Action | Private Scope | Shared Scope | External Sources |
|--------|--------------|--------------|------------------|
| **Create Collection** | ✅ User | 🔒 Admin only | N/A |
| **Delete Collection** | ✅ Owner | 🔒 Admin only | N/A |
| **Ingest Document** | ✅ User | ✅ All members | N/A |
| **Delete Document** | ✅ Owner | 🔒 Admin only | N/A |
| **Query** | ✅ Owner | ✅ All members | ✅ All members |

## 🔄 Processing Pipelines

### Ingestion Pipeline (IngestOrchestrator)

```
PDF Upload
    ↓
┌──────────────────┐
│ ValidationStage  │ → Format check, size limit, duplicate detection
└──────────────────┘
    ↓
┌──────────────────┐
│  ParsingStage    │ → PyMuPDF text extraction
└──────────────────┘
    ↓
┌──────────────────┐
│ ChunkingStage    │ → Token-based splitting (512/50)
└──────────────────┘
    ↓
┌──────────────────┐
│ EmbeddingStage   │ → OpenAI embeddings (1536 dim)
└──────────────────┘
    ↓
┌──────────────────┐
│ IndexingStage    │ → Milvus HNSW index insertion
└──────────────────┘
    ↓
┌──────────────────┐
│  StorageStage    │ → MinIO upload (PDF + chunks)
└──────────────────┘
    ↓
┌──────────────────┐
│  ConsumeStage    │ → Auth service usage tracking
└──────────────────┘
    ↓
  Success!
```

### Query Pipeline (QueryOrchestrator)

```
User Query
    ↓
┌──────────────────────────┐
│  Source Analysis         │ → Analyze sources & collections
└──────────────────────────┘
    ↓
┌──────────────────────────┐
│  Handler Creation        │ → Create CollectionHandler, ExternalHandlers
└──────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│         Parallel Execution (asyncio)            │
├──────────────┬──────────────┬──────────────────┤
│ Collection   │  MEVZUAT     │     KARAR        │
│ Handler      │  Handler     │     Handler      │
│   (Milvus)   │  (External)  │   (External)     │
└──────────────┴──────────────┴──────────────────┘
    ↓           ↓              ↓
┌──────────────────────────────────────────────────┐
│          Result Aggregation                      │
│  - Merge sources from all handlers              │
│  - Deduplicate and rank by relevance            │
│  - Filter by min_relevance_score                │
└──────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────┐
│          LLM Answer Generation                   │
│  - Create prompt with aggregated sources        │
│  - Call GPT-4o-mini                             │
│  - Apply tone and language options              │
└──────────────────────────────────────────────────┘
    ↓
  Response
```

## 🌐 Web Interfaces

Sistem başladıktan sonra şu arayüzlere erişebilirsiniz:

- 📖 **API Docs**: http://localhost:8080/docs (Swagger UI)
  - Interactive API testing
  - 🔒 Authorize button ile token girebilirsiniz

- 🗄️ **MinIO Console**: http://localhost:9001
  - Login: `minioadmin` / `minioadmin`
  - Bucket'ları ve dosyaları görüntüleyin

- 🔍 **Milvus Attu**: http://localhost:8000
  - Vector database yönetimi
  - Collection'ları ve index'leri görüntüleyin

## 🧪 Testing

### Test Structure
```bash
tests/
├── unit/              # Unit tests (fast, no external deps)
├── integration/       # Integration tests (requires Docker)
└── conftest.py       # Shared fixtures
```

### Test Commands
```bash
# Tüm testleri çalıştır
make test
# veya
pytest

# Sadece unit testler
make test-unit
# veya
pytest -m unit

# Sadece integration testler
make test-integration
# veya
pytest -m integration

# Coverage raporu
pytest --cov=app --cov=api --cov-report=html:test_output/htmlcov
```

### Test Markers
- `unit`: Fast, isolated tests
- `integration`: Requires Docker services
- `docker`: Docker-dependent tests
- `api`: API endpoint tests
- `storage`: MinIO/Milvus tests
- `embedding`: Embedding generation tests
- `chunk`: Chunking tests

## 🛠️ Development

### Proje Yapısı
```
Onedocs-RAG-Project/
├── api/                           # FastAPI endpoints
│   ├── main.py                    # FastAPI app entry point
│   ├── endpoints/                 # Endpoint modules
│   │   ├── query.py              # POST /chat/process
│   │   ├── ingest.py             # POST /ingest
│   │   ├── collections.py        # Collection CRUD
│   │   └── documents.py          # Document management
│   └── core/                      # Core services
│       ├── milvus_manager.py     # Milvus operations
│       ├── embeddings.py         # Embedding service
│       └── dependencies.py       # FastAPI dependencies
│
├── app/                           # Business logic
│   ├── core/
│   │   ├── auth.py               # JWT authentication
│   │   ├── orchestrator/         # Orchestrator pattern
│   │   │   ├── orchestrator.py  # QueryOrchestrator
│   │   │   ├── aggregator.py    # ResultAggregator
│   │   │   └── handlers/        # Search handlers
│   │   ├── storage/              # MinIO operations
│   │   ├── chunking/             # Text chunking strategies
│   │   ├── embeddings/           # Embedding providers
│   │   └── generation/           # LLM response generation
│   ├── pipelines/                # Processing pipelines
│   │   ├── ingest_pipeline.py   # Document ingestion
│   │   └── query_pipeline.py    # Query processing
│   └── config/
│       └── settings.py           # Configuration
│
├── schemas/                       # Pydantic models
│   ├── api/
│   │   ├── requests/             # Request models
│   │   └── responses/            # Response models
│   └── validation.py             # Validation models
│
├── tests/                         # Test suite
├── docker-compose.yml            # Docker orchestration
└── requirements.txt              # Python dependencies
```

### Local Development
```bash
# Virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Dependencies
pip install -r requirements.txt

# Development server (auto-reload)
make run

# Code formatting (opsiyonel)
black app/ api/
isort app/ api/
```

### Debugging

**Docker servislerini kontrol et:**
```bash
docker compose ps
docker compose logs -f milvus
docker compose logs -f minio
```

**Milvus bağlantısını test et:**
```bash
python -c "from pymilvus import connections; connections.connect('default', host='localhost', port='19530'); print('✅ Connected!')"
```

**MinIO bağlantısını test et:**
```bash
python -c "from minio import Minio; client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False); print('✅ Connected!')"
```

**Collection'ları listele:**
```bash
python -c "
from pymilvus import connections, utility
connections.connect('default', host='localhost', port='19530')
print('Collections:', utility.list_collections())
"
```

### Common Issues

**Port conflict:**
```bash
# Kullanılan portları kontrol et
lsof -i :8080,9000,19530

# Process'i kill et
kill -9 $(lsof -t -i:8080)
```

**Docker memory:**
```bash
# Docker Desktop'ta memory'yi 8GB+'ya çıkarın
docker system prune -a --volumes
```

**Auth errors:**
```bash
# JWT_SECRET_KEY'in Auth Service ile aynı olduğundan emin olun
grep JWT_SECRET_KEY .env

# Development için auth'u kapat
echo "REQUIRE_AUTH=false" >> .env
```

## 📊 Performance

### Typical Processing Times
- **PDF İşleme**: ~2-5 saniye (sayfa başına)
- **Embedding Üretimi**: ~500ms (OpenAI API)
- **Vector Search**: <100ms
- **LLM Answer Generation**: ~1-3 saniye
- **Total Query Time**: <5 saniye

### Resource Requirements
- **RAM**: Minimum 8GB, önerilen 16GB
- **CPU**: Multi-core önerilir
- **Disk**: ~10GB (Docker images + data)
- **Network**: Stabil internet (OpenAI API için)

## 🔒 Security Best Practices

1. **JWT Secret**: Production'da güçlü secret key kullanın
2. **HTTPS**: Reverse proxy (Nginx/Traefik) ile HTTPS aktif edin
3. **Rate Limiting**: API endpoint'lerine rate limiting ekleyin
4. **Input Validation**: Tüm user input'ları validate edilir (Pydantic)
5. **Scope Isolation**: Multi-tenant data otomatik olarak izole edilir
6. **Permission Checks**: Her endpoint JWT ve permission kontrolü yapar

## 📄 Lisans

MIT License

## 🙏 Teşekkürler

- **OpenAI**: GPT-4 ve embedding modelleri
- **Milvus**: Yüksek performanslı vector database
- **MinIO**: S3-compatible object storage
- **FastAPI**: Modern Python web framework

---

**🚀 Production Ready** | **📦 Docker-based** | **🔐 Secure & Isolated** | **⚡ High Performance**

**Made with ❤️ by OneDocs Team**
