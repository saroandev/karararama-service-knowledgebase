 Orchestrator Servis Ayrıştırma Planı

 Kararlar
 ┌──────────────────────────────────────┬─────────────────────────────────────┐
 │                Karar                 │                Seçim                │
 ├──────────────────────────────────────┼─────────────────────────────────────┤
 │ Yeni servis ismi                     │ onedocs-service-orchestrator        │
 ├──────────────────────────────────────┼─────────────────────────────────────┤
 │ Conversation yönetimi                │ Bu serviste (knowledgebase) kalacak │
 ├──────────────────────────────────────┼─────────────────────────────────────┤
 │ Usage tracking                       │ Her serviste ayrı ayrı              │
 ├──────────────────────────────────────┼─────────────────────────────────────┤
 │ /chat/process                        │ Basitleştirilip kalacak             │
 ├──────────────────────────────────────┼─────────────────────────────────────┤
 │ Orchestrator'ın bu servisi çağırması │ Mevcut /api/collections/query       │
 ├──────────────────────────────────────┼─────────────────────────────────────┤
 │ Yeni servis                          │ Ayrı repo oluşturulacak             │
 └──────────────────────────────────────┴─────────────────────────────────────┘
 ---
 Mevcut Mimari

 ┌─────────────────────────────────────────────────────────────────┐
 │            onedocs-service-knowledgebase (Port: 8080)           │
 ├─────────────────────────────────────────────────────────────────┤
 │  POST /chat/process                                             │
 │       │                                                         │
 │       ▼                                                         │
 │  ┌─────────────────────┐                                        │
 │  │  QueryOrchestrator  │ ◄── TAŞINACAK                          │
 │  └─────────────────────┘                                        │
 │       │                                                         │
 │       ├──────────────────┬──────────────────┐                   │
 │       ▼                  ▼                  ▼                   │
 │  ┌──────────┐    ┌──────────────┐    ┌────────────────┐         │
 │  │Collection│    │  External    │    │   LLM-Only     │         │
 │  │ Handler  │    │   Handler    │    │   Response     │         │
 │  └──────────┘    └──────────────┘    └────────────────┘         │
 │       │                  │               TAŞINACAK              │
 │       │                  │                                      │
 │       ▼                  ▼                                      │
 │  ┌─────────────────────────────────────────────────────┐        │
 │  │              ResultAggregator  ◄── TAŞINACAK        │        │
 │  └─────────────────────────────────────────────────────┘        │
 │                                                                 │
 │  POST /api/collections/query  ◄── KALACAK (zaten var)           │
 │  POST /api/collections/*      ◄── KALACAK                       │
 │  POST /api/documents/*        ◄── KALACAK                       │
 │  GET  /health                 ◄── KALACAK                       │
 │  POST /conversations/*        ◄── KALACAK                       │
 └─────────────────────────────────────────────────────────────────┘

 ---
 Hedef Mimari

 ┌─────────────────────────────────────────────────────────────────┐
 │          onedocs-service-orchestrator (Port: 8090)              │
 ├─────────────────────────────────────────────────────────────────┤
 │  POST /chat/process                                             │
 │       │                                                         │
 │       ▼                                                         │
 │  ┌─────────────────────┐                                        │
 │  │  QueryOrchestrator  │                                        │
 │  └─────────────────────┘                                        │
 │       │                                                         │
 │       ├──────────────────┬──────────────────┐                   │
 │       ▼                  ▼                  ▼                   │
 │  ┌──────────┐    ┌──────────────┐    ┌────────────────┐         │
 │  │Collection│    │  External    │    │   LLM-Only     │         │
 │  │ Handler  │    │   Handler    │    │   Response     │         │
 │  └──────────┘    └──────────────┘    └────────────────┘         │
 │       │                  │                                      │
 │       │                  │                                      │
 │       ▼                  ▼                                      │
 │  ┌─────────────────────────────────────────────────────┐        │
 │  │              ResultAggregator                       │        │
 │  └─────────────────────────────────────────────────────┘        │
 └─────────────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
 ┌─────────────────────┐    ┌────────────────┐
 │ onedocs-service-    │    │  Global DB     │
 │ knowledgebase       │    │  (Port: 8070)  │
 │ (Port: 8080)        │    └────────────────┘
 │                     │
 │ Endpoint'ler:       │
 │ • /api/collections/ │
 │   query             │
 │ • /chat/process     │
 │   (basitleştirilmiş)│
 │ • /conversations/*  │
 │ • /api/documents/*  │
 └─────────────────────┘

 ---
 Bu Serviste (knowledgebase) Yapılacaklar

 1. /chat/process Endpoint'ini Basitleştir

 Dosya: api/endpoints/query.py

 Mevcut durum: QueryOrchestrator kullanıyor
 Hedef: Sadece collection query yapan basit endpoint

 Yeni davranış:
 - sources parametresi verilirse → Hata dön (orchestrator'a yönlendir)
 - Sadece collections parametresi verilirse → /api/collections/query çağır
 - Ne collections ne sources yoksa → LLM-only response (opsiyonel, kaldırılabilir)

 2. Kaldırılacak Dosyalar

 app/core/orchestrator/
 ├── __init__.py           → KALDIRILACAK (veya sadeleştirilecek)
 ├── orchestrator.py       → KALDIRILACAK
 ├── aggregator.py         → KALDIRILACAK
 ├── prompts.py            → KALACAK (collection_query kullanıyor)
 └── handlers/
     ├── __init__.py       → KALDIRILACAK
     ├── base.py           → KALDIRILACAK
     ├── collection_handler.py → KALDIRILACAK
     └── external_handler.py   → KALDIRILACAK

 3. Kaldırılacak/Güncellenecek Service'ler

 - app/services/global_db_service.py → KALDIRILACAK (orchestrator kullanacak)

 4. Conversation Yönetimi

 - app/core/conversation.py → KALACAK
 - api/endpoints/conversations.py → KALACAK
 - Orchestrator servisi conversation endpoint'lerini HTTP ile çağıracak

 ---
 Yeni Servis (orchestrator) İçin Gerekli Dosyalar

 Taşınacak Dosyalar

 onedocs-service-orchestrator/
 ├── api/
 │   ├── main.py
 │   └── endpoints/
 │       └── chat.py              ← query.py'den uyarlanacak
 ├── app/
 │   ├── config/
 │   │   └── settings.py          ← Yeni config
 │   ├── core/
 │   │   ├── auth.py              ← Kopyalanacak (JWT validation)
 │   │   └── orchestrator/
 │   │       ├── __init__.py
 │   │       ├── orchestrator.py  ← Taşınacak
 │   │       ├── aggregator.py    ← Taşınacak
 │   │       ├── prompts.py       ← Taşınacak
 │   │       └── handlers/
 │   │           ├── __init__.py
 │   │           ├── base.py           ← Taşınacak
 │   │           ├── collection_handler.py ← Güncellenerek taşınacak
 │   │           └── external_handler.py   ← Taşınacak
 │   └── services/
 │       ├── global_db_service.py     ← Taşınacak
 │       ├── auth_service.py          ← Kopyalanacak (usage tracking)
 │       └── knowledgebase_service.py ← YENİ (bu servisi çağıracak)
 ├── schemas/
 │   └── ...                      ← Gerekli schema'lar kopyalanacak
 ├── requirements.txt
 ├── Dockerfile
 └── docker-compose.yml

 Yeni Servis Config'i

 # onedocs-service-orchestrator/app/config/settings.py

 # Servis URL'leri
 KNOWLEDGEBASE_SERVICE_URL = "http://localhost:8080"  # Bu servis
 GLOBAL_DB_SERVICE_URL = "http://localhost:8070"
 AUTH_SERVICE_URL = "http://localhost:8001"

 # Timeout'lar
 KNOWLEDGEBASE_SERVICE_TIMEOUT = 30
 GLOBAL_DB_SERVICE_TIMEOUT = 30

 ---
 API Değişiklikleri

 Bu Serviste (Basitleştirilmiş /chat/process)

 @router.post("/chat/process")
 async def query_documents(request: QueryRequest, ...):
     # Sources varsa hata
     if request.sources:
         raise HTTPException(
             status_code=400,
             detail="Bu endpoint sadece collection sorguları için. "
                    "External sources için orchestrator servisini kullanın."
         )

     # Collections varsa → /api/collections/query'e yönlendir
     if request.collections:
         return await _forward_to_collections_query(request, user)

     # Hiçbiri yoksa → Hata veya LLM-only
     raise HTTPException(
         status_code=400,
         detail="En az bir collection belirtmelisiniz."
     )

 Orchestrator'da (Yeni /chat/process)

 @router.post("/chat/process")
 async def process_chat(request: QueryRequest, ...):
     orchestrator = QueryOrchestrator()

     # Mevcut mantık aynen çalışır
     # CollectionHandler → localhost:8080/api/collections/query
     # ExternalHandler → localhost:8070/query/search

     return await orchestrator.execute_query(request, user, token)

 ---
 Conversation Entegrasyonu

 Orchestrator servisi conversation yönetimi için bu servisi çağıracak:

 # onedocs-service-orchestrator/app/services/knowledgebase_service.py

 class KnowledgebaseServiceClient:
     async def save_conversation_message(
         self,
         conversation_id: str,
         role: str,
         content: str,
         user_token: str
     ):
         """Conversation mesajı kaydet"""
         async with httpx.AsyncClient() as client:
             response = await client.post(
                 f"{KNOWLEDGEBASE_URL}/conversations/{conversation_id}/messages",
                 headers={"Authorization": f"Bearer {user_token}"},
                 json={"role": role, "content": content}
             )
         return response.json()

     async def get_conversation_context(
         self,
         conversation_id: str,
         user_token: str,
         max_messages: int = 10
     ):
         """Conversation context'i getir"""
         async with httpx.AsyncClient() as client:
             response = await client.get(
                 f"{KNOWLEDGEBASE_URL}/conversations/{conversation_id}/context",
                 headers={"Authorization": f"Bearer {user_token}"},
                 params={"max_messages": max_messages}
             )
         return response.json()

 ---
 Uygulama Adımları

 Faz 1: Bu Servisi Hazırla (Önce)

 1. /chat/process endpoint'ini basitleştir
 2. Conversation endpoint'lerinin orchestrator'dan çağrılabilir olduğunu doğrula
 3. Gereksiz orchestrator kodlarını kaldır
 4. Test et: /api/collections/query bağımsız çalışıyor mu?

 Faz 2: Yeni Servis Oluştur (Sonra)

 1. Yeni repo oluştur: onedocs-service-orchestrator
 2. Taşınacak dosyaları kopyala
 3. Config ayarla (servis URL'leri)
 4. KnowledgebaseServiceClient yaz
 5. CollectionHandler'ı güncelle (yeni URL)
 6. Docker compose'a ekle
 7. Test et: Tüm flow çalışıyor mu?

 Faz 3: Entegrasyon (En Son)

 1. Frontend'i yeni orchestrator endpoint'ine yönlendir
 2. Eski /chat/process'i deprecate et
 3. Monitoring/logging ekle

 ---
 Test Planı

 Bu Serviste Test

 # 1. Collections query bağımsız çalışıyor mu?
 curl -X POST localhost:8080/api/collections/query \
   -H "Authorization: Bearer $TOKEN" \
   -d '{"question": "test", "collections": [{"name": "test", "scopes": ["private"]}]}'

 # 2. Basitleştirilmiş /chat/process
 curl -X POST localhost:8080/chat/process \
   -H "Authorization: Bearer $TOKEN" \
   -d '{"question": "test", "collections": [{"name": "test", "scopes": ["private"]}]}'

 # 3. Sources ile hata veriyor mu?
 curl -X POST localhost:8080/chat/process \
   -H "Authorization: Bearer $TOKEN" \
   -d '{"question": "test", "sources": ["mevzuat"]}'
 # Beklenen: 400 Bad Request

 Orchestrator Serviste Test

 # 1. Tam flow testi
 curl -X POST localhost:8090/chat/process \
   -H "Authorization: Bearer $TOKEN" \
   -d '{
     "question": "test",
     "conversation_id": "conv-123",
     "sources": ["mevzuat"],
     "collections": [{"name": "test", "scopes": ["private"]}]
   }'

 # 2. Sadece sources
 curl -X POST localhost:8090/chat/process \
   -d '{"question": "test", "sources": ["mevzuat"]}'

 # 3. Sadece collections
 curl -X POST localhost:8090/chat/process \
   -d '{"question": "test", "collections": [...]}'

 ---
 Dosya Referansları
 ┌───────────────────────────────────────┬─────────┬──────────────────────────┐
 │          Bu Servisteki Dosya          │  Satır  │         Aksiyon          │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ api/endpoints/query.py                │ 22-88   │ Basitleştirilecek        │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ app/core/orchestrator/orchestrator.py │ 21-313  │ Kaldırılacak             │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ app/core/orchestrator/aggregator.py   │ 22-761  │ Kaldırılacak             │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ app/core/orchestrator/handlers/*.py   │ *       │ Kaldırılacak             │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ app/services/global_db_service.py     │ 15-394  │ Kaldırılacak             │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ api/endpoints/collections_query.py    │ 151-676 │ Kalacak (değişiklik yok) │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ api/endpoints/conversations.py        │ *       │ Kalacak                  │
 ├───────────────────────────────────────┼─────────┼──────────────────────────┤
 │ app/core/conversation.py              │ *       │ Kalacak                  │
 └───────────────────────────────────────┴─────────┴──────────────────────────┘



 ● Faz 1 Tamamlandı

  Bu serviste yapılan değişiklikler:

  1. /chat/process Basitleştirildi

  - Artık sadece collection sorguları kabul ediyor
  - sources parametresi verilirse 400 hatası dönüyor
  - /api/collections/query fonksiyonunu dahili olarak çağırıyor

  2. Conversation Endpoint'leri Eklendi

  Orchestrator servisi için iki yeni endpoint:
  - POST /conversations/{id}/messages - Mesaj kaydetme
  - GET /conversations/{id}/context - LLM context alma

  3. Orchestrator Kodları Kaldırıldı

  Silinen dosyalar:
  - app/core/orchestrator/orchestrator.py
  - app/core/orchestrator/aggregator.py
  - app/core/orchestrator/handlers/ (tüm klasör)

  Kalan dosyalar:
  - ingest_orchestrator.py (document ingestion için)
  - prompts.py (collections_query kullanıyor)

  4. Health Check Güncellendi

  - Global DB kontrolü kaldırıldı
  - Sadece Milvus ve MinIO kontrol ediliyor

  Sonraki Adımlar (Faz 2)

  Yeni onedocs-service-orchestrator reposu oluşturup:
  1. Taşınan orchestrator kodlarını eklemek
  2. KnowledgebaseServiceClient yazmak
  3. CollectionHandler'ı bu servise yönlendirmek


  ● Tüm testler başarılı.

  Test Sonuçları
  ┌─────────────────────┬───────────────────────────────────┬────────────────────────────────┐
  │        Test         │             Endpoint              │             Sonuç              │
  ├─────────────────────┼───────────────────────────────────┼────────────────────────────────┤
  │ Health Check        │ GET /health                       │ ✅ Çalışıyor (global_db: null) │
  ├─────────────────────┼───────────────────────────────────┼────────────────────────────────┤
  │ Sources ile istek   │ POST /chat/process                │ ✅ 400 hatası veriyor          │
  ├─────────────────────┼───────────────────────────────────┼────────────────────────────────┤
  │ Collections olmadan │ POST /chat/process                │ ✅ 400 hatası veriyor          │
  ├─────────────────────┼───────────────────────────────────┼────────────────────────────────┤
  │ Collections ile     │ POST /chat/process                │ ✅ Çalışıyor                   │
  ├─────────────────────┼───────────────────────────────────┼────────────────────────────────┤
  │ Mesaj kaydetme      │ POST /conversations/{id}/messages │ ✅ Çalışıyor                   │
  ├─────────────────────┼───────────────────────────────────┼────────────────────────────────┤
  │ LLM Context         │ GET /conversations/{id}/context   │ ✅ Çalışıyor                   │
  └─────────────────────┴───────────────────────────────────┴────────────────────────────────┘
  Servis Faz 1 için hazır. Orchestrator servisi bu endpoint'leri kullanabilir:
  - POST /api/collections/query - Collection sorguları
  - POST /conversations/{id}/messages - Mesaj kaydetme
  - GET /conversations/{id}/context - LLM context almatama




  ● Faz 2 tamamlandı. Orchestrator servisi başarıyla oluşturuldu ve test edildi.

  Özet - Faz 2 (Orchestrator Servis Oluşturma)

  Oluşturulan dosyalar (/home/ugur/onedocs/onedocs-service-orchestrator/):

  Proje Yapısı:
  onedocs-service-orchestrator/
  ├── api/
  │   ├── __init__.py
  │   ├── main.py                      # FastAPI uygulaması
  │   └── endpoints/
  │       ├── __init__.py
  │       ├── health.py                # Health check endpoint
  │       └── chat.py                  # /chat/process endpoint
  ├── app/
  │   ├── __init__.py
  │   ├── config/
  │   │   ├── __init__.py
  │   │   ├── settings.py              # Konfigürasyon
  │   │   └── constants.py             # ServiceType constants
  │   ├── core/
  │   │   ├── auth.py                  # JWT validation
  │   │   ├── exceptions.py            # Custom exceptions
  │   │   └── orchestrator/
  │   │       ├── __init__.py
  │   │       ├── orchestrator.py      # Ana orchestrator (güncellenmiş)
  │   │       ├── aggregator.py        # Result aggregator (güncellenmiş)
  │   │       ├── prompts.py
  │   │       └── handlers/
  │   │           ├── __init__.py
  │   │           ├── base.py
  │   │           ├── collection_handler.py  (güncellenmiş)
  │   │           └── external_handler.py
  │   └── services/
  │       ├── __init__.py
  │       ├── auth_service.py          # Usage tracking
  │       ├── global_db_service.py     # External source queries
  │       └── knowledgebase_service.py # YENİ - HTTP client
  ├── schemas/
  │   └── api/
  │       ├── requests/
  │       │   ├── query.py
  │       │   └── scope.py
  │       └── responses/
  │           └── query.py
  ├── requirements.txt
  ├── Dockerfile
  ├── docker-compose.yml
  ├── Makefile
  └── .env.example

  Yapılan Değişiklikler:
  1. conversation_manager → knowledgebase_service HTTP client'a dönüştürüldü
  2. storage bağımlılığı kaldırıldı (document_url'ler Knowledgebase'den geliyor)
  3. collection_handler settings URL'sini kullanıyor
  4. Tüm conversation işlemleri HTTP üzerinden yapılıyor

  Servis Test Sonucu:
  - Health endpoint çalışıyor
  - Knowledgebase servisi ile bağlantı OK
  - Global DB servisi ile bağlantı OK

  Servisi başlatmak için:
  cd /home/ugur/onedocs/onedocs-service-orchestrator
  make run
  # veya
  make docker-up



   Faz 3 tamamlandı. Şimdi yaptığım değişikliklerin özetini vereyim:

  Orchestrator'a Eklenenler:

  1. Database katmanı:
    - app/core/database.py - PostgreSQL connection manager
    - migrations/init.sql - conversation_log tablosu
    - settings.py - PostgreSQL config eklendi
  2. Conversation katmanı:
    - app/core/conversation.py - ConversationManager
    - schemas/api/responses/conversation.py - Response schemas (UUID formatında)
    - api/endpoints/conversations.py - Conversation endpoints
  3. Güncellemeler:
    - orchestrator.py - HTTP çağrıları → doğrudan conversation_manager
    - aggregator.py - HTTP çağrıları → doğrudan conversation_manager
    - knowledgebase_service.py - Sadece query_collections() kaldı
    - health.py - PostgreSQL health check eklendi
    - docker-compose.yml - PostgreSQL servisi eklendi
    - requirements.txt - psycopg2-binary, sqlalchemy eklendi

  Knowledgebase'den Silinenler:

  - app/core/conversation.py
  - app/core/database.py
  - api/endpoints/conversations.py
  - schemas/api/responses/conversation.py
  - main.py'den conversations router kaldırıldı


  