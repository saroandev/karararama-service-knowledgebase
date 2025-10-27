# Presigned URL Endpoint Documentation

## 📌 Genel Bakış

Bu doküman, **KnowledgeBase Service** ve **Global DB Service**'te implement edilen `/docs/presign` endpoint'inin çalışma mantığını açıklar.

**Amaç**: Citations'dan dönen `document_url` ile PDF dokümanlarının tarayıcıda **inline** (indirmeden) görüntülenmesini sağlamak.

---

## 🎯 Endpoint Detayları

### **Endpoint**
```
POST /docs/presign
```

### **Authentication**
- **Required**: JWT Bearer Token
- Header: `Authorization: Bearer {token}`

### **Request Body**
```json
{
  "document_url": "http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf?X-Amz-Signature=...",
  "expires_seconds": 3600
}
```

**Parameters:**
- `document_url` (string, required): Citations'dan gelen doküman URL'i
- `expires_seconds` (integer, optional): Presigned URL'in geçerlilik süresi (saniye)
  - Default: 3600 (1 saat)
  - Minimum: 300 (5 dakika)
  - Maximum: 86400 (24 saat)

### **Response**
```json
{
  "url": "http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf?response-content-type=application%2Fpdf&response-content-disposition=inline&X-Amz-Signature=...",
  "expires_in": 3600,
  "document_id": "doc-123",
  "source_type": "collection"
}
```

**Response Fields:**
- `url` (string): Inline görüntüleme için presigned URL
- `expires_in` (integer): URL'in geçerlilik süresi (saniye)
- `document_id` (string): Doküman ID'si
- `source_type` (string): Kaynak türü (`"collection"` veya `"external"`)

---

## 🔍 Endpoint Mantığı

### **1. URL Parsing ve Source Type Detection**

Gelen `document_url` parse edilerek dokümanın **collection** (local MinIO) mu yoksa **external source** (Global DB) mu olduğu belirlenir.

```python
from urllib.parse import urlparse

def _is_collection_document(hostname: str) -> bool:
    """
    URL hostname'ine bakarak collection mu external source mu belirle

    Args:
        hostname: URL'den parse edilen hostname

    Returns:
        True: Collection document (local MinIO)
        False: External source (Global DB MinIO)
    """
    minio_endpoint_host = settings.MINIO_ENDPOINT.split(":")[0]
    minio_hosts = ["minio", "localhost", "127.0.0.1", minio_endpoint_host]

    return hostname in minio_hosts
```

**Örnekler:**

| URL | Hostname | Source Type |
|-----|----------|-------------|
| `http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf` | `minio` | **collection** |
| `http://localhost:9000/org-abc/users/xyz/docs/doc-123/file.pdf` | `localhost` | **collection** |
| `http://external-minio:9000/mevzuat/tuzukler/doc-456/file.pdf` | `external-minio` | **external** |

---

### **2. Collection Document (Senaryo 1)**

Doküman local MinIO'da ise direkt presigned URL oluşturulur.

#### **2.1. URL'den Bucket ve Object Key Çıkarma**

```python
def _extract_minio_path(url: str) -> tuple:
    """
    MinIO URL'inden bucket ve object_key çıkar

    Args:
        url: MinIO presigned URL

    Returns:
        (bucket_name, object_key) tuple

    Example:
        Input: "http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf?X-Amz-..."
        Output: ("org-abc", "users/xyz/docs/doc-123/file.pdf")
    """
    parsed = urlparse(url)
    path = parsed.path.lstrip("/").split("?")[0]
    path_parts = path.split("/")

    if len(path_parts) < 2:
        raise ValueError(f"Invalid MinIO URL format: {url}")

    bucket = path_parts[0]
    object_key = "/".join(path_parts[1:])

    return bucket, object_key
```

#### **2.2. Document ID Çıkarma**

```python
def _extract_document_id_from_url(url: str) -> str:
    """
    URL path'inden document_id çıkar

    Args:
        url: Document URL

    Returns:
        document_id

    Example:
        Input: "/users/xyz/docs/doc-123/file.pdf"
        Output: "doc-123"
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]

    # "docs" klasörünü bul, bir sonraki part document_id'dir
    if "docs" in path_parts:
        docs_idx = path_parts.index("docs")
        if docs_idx + 1 < len(path_parts):
            return path_parts[docs_idx + 1]

    raise ValueError(f"Cannot extract document_id from URL: {url}")
```

#### **2.3. Presigned URL Oluşturma (Inline Headers ile)**

```python
from datetime import timedelta

# MinIO client'ı al
client = storage.client_manager.get_client()

# Presigned URL oluştur
presigned_url = client.presigned_get_object(
    bucket,
    object_key,
    expires=timedelta(seconds=expires_seconds),
    response_headers={
        "response-content-type": "application/pdf",
        "response-content-disposition": "inline"  # ⚠️ ÖNEMLİ: "attachment" değil!
    }
)
```

**⚠️ CRITICAL**: `response-content-disposition` header'ı **"inline"** olmalı, **"attachment"** olmamalı! Aksi takdirde tarayıcı dosyayı indirmeye çalışır.

---

### **3. External Source (Senaryo 2)**

Doküman external source'dan (Global DB) ise, **tüm `document_url`** Global DB Service'e forward edilir.

#### **3.1. External Source Detection**

```python
parsed_url = urlparse(request.document_url)
is_collection = _is_collection_document(parsed_url.hostname)

if not is_collection:
    # External source - Global DB'ye forward et
    ...
```

#### **3.2. Global DB Service'e İstek (Forward)**

**KnowledgeBase → Global DB Service Request:**

```
POST http://localhost:8070/docs/presign
Authorization: Bearer {user_token}
Content-Type: application/json

{
  "document_url": "http://external-minio:9000/mevzuat/tuzukler/doc-456/file.pdf",
  "expires_seconds": 3600
}
```

**Global DB Service Response:**
```json
{
  "url": "http://external-minio:9000/mevzuat/tuzukler/doc-456/file.pdf?response-content-type=application%2Fpdf&response-content-disposition=inline&X-Amz-Signature=...",
  "expires_in": 3600,
  "document_id": "doc-456",
  "source_type": "external"
}
```

**KnowledgeBase Service'teki kod:**

```python
# Global DB client ile presign request'i forward et
global_db_client = get_global_db_client()

# Tüm document_url'i Global DB'ye gönder
result = await global_db_client.get_presigned_url_from_external(
    document_url=request.document_url,  # Tüm URL forward edilir
    user_token=user.raw_token,
    expires_seconds=request.expires_seconds
)

# Global DB'den dönen response kontrol et
if not result.get("url"):
    raise HTTPException(500, "Failed to get presigned URL from Global DB")

# Global DB'den dönen response'u kullan
return PresignedUrlResponse(
    url=result["url"],
    expires_in=result["expires_in"],
    document_id=result["document_id"],
    source_type=result.get("source_type", "external")
)
```

**Önemli**: KnowledgeBase Service, external source için **proxy görevi görür**. URL parsing ve MinIO işlemleri Global DB Service'te yapılır.

---

## 🛠️ Global DB Service Implementation Guide

Global DB Service'te aynı endpoint'i implement etmek için:

### **1. Endpoint Tanımı**

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import timedelta
from urllib.parse import urlparse

router = APIRouter()

class PresignedUrlRequest(BaseModel):
    document_url: str = Field(..., description="Document URL")
    expires_seconds: int = Field(default=3600, ge=300, le=86400)

class PresignedUrlResponse(BaseModel):
    url: str
    expires_in: int
    document_id: str
    source_type: str = "external"

@router.post("/docs/presign", response_model=PresignedUrlResponse)
async def get_presigned_url(
    request: PresignedUrlRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Generate presigned URL for inline document viewing
    """
    try:
        # 1. URL'den bucket ve object_key çıkar
        bucket, object_key = _extract_minio_path(request.document_url)

        # 2. Document ID çıkar
        document_id = _extract_document_id_from_url(request.document_url)

        # 3. MinIO presigned URL oluştur (inline headers ile)
        presigned_url = minio_client.presigned_get_object(
            bucket,
            object_key,
            expires=timedelta(seconds=request.expires_seconds),
            response_headers={
                "response-content-type": "application/pdf",
                "response-content-disposition": "inline"
            }
        )

        return PresignedUrlResponse(
            url=presigned_url,
            expires_in=request.expires_seconds,
            document_id=document_id,
            source_type="external"
        )

    except ValueError as e:
        raise HTTPException(400, f"Invalid URL format: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Failed to generate presigned URL: {str(e)}")
```

### **2. Helper Functions (Aynı Mantık)**

Yukarıda tanımlanan helper functions'ları Global DB Service'te de kullanın:
- `_extract_minio_path(url)` → Bucket ve object_key çıkarma
- `_extract_document_id_from_url(url)` → Document ID parsing

---

## 🔐 Authentication

### **UserContext ve JWT Token**

Endpoint JWT authentication gerektiriyor. `UserContext`'te **raw_token** field'ı olmalı:

```python
class UserContext(BaseModel):
    user_id: str
    organization_id: str
    email: str
    role: str = "member"
    permissions: List[str] = []
    raw_token: str = ""  # ⚠️ External service çağrıları için gerekli
```

`get_current_user()` dependency'sinde token'ı sakla:

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> UserContext:
    token = credentials.credentials
    payload = decode_jwt_token(token)

    return UserContext(
        user_id=payload["user_id"],
        organization_id=payload["organization_id"],
        email=payload["email"],
        raw_token=token  # ⚠️ Raw token'ı sakla
    )
```

---

## 📊 URL Format Örnekleri

### **Collection Document (Local MinIO)**

```
http://minio:9000/org-abc123/users/user-xyz/docs/doc-789/file.pdf?X-Amz-Signature=...

Parse Result:
├── bucket: "org-abc123"
├── object_key: "users/user-xyz/docs/doc-789/file.pdf"
├── document_id: "doc-789"
└── source_type: "collection"
```

### **External Source (Global DB MinIO)**

```
http://external-minio:9000/mevzuat/tuzukler/bf80d5af-bfbc-4475-b1ef-10badd148f6d/file.pdf

Parse Result:
├── bucket: "mevzuat"
├── object_key: "tuzukler/bf80d5af-bfbc-4475-b1ef-10badd148f6d/file.pdf"
├── document_id: "bf80d5af-bfbc-4475-b1ef-10badd148f6d"
└── source_type: "external"
```

---

## ⚠️ Önemli Notlar

### **1. Inline Display Headers**

Presigned URL oluştururken **mutlaka** bu header'ları ekleyin:

```python
response_headers={
    "response-content-type": "application/pdf",
    "response-content-disposition": "inline"  # ❌ "attachment" değil!
}
```

**Neden?**
- `inline`: Tarayıcıda PDF viewer ile görüntülenir
- `attachment`: Dosya indirilir (kullanıcı deneyimini bozar)

### **2. URL Expiry**

- Minimum: 300 saniye (5 dakika)
- Maximum: 86400 saniye (24 saat)
- Default: 3600 saniye (1 saat)

### **3. Error Handling**

```python
# URL parsing hatası
ValueError: "Invalid MinIO URL format"
ValueError: "Cannot extract document_id from URL"

# MinIO hatası
HTTPException(500, "Failed to generate presigned URL")

# Auth hatası
HTTPException(401, "Token unavailable")
```

---

## 🧪 Test Senaryoları

### **Test 1: Collection Document**

**Request:**
```bash
curl -X POST http://localhost:8080/docs/presign \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf",
    "expires_seconds": 3600
  }'
```

**Expected Response:**
```json
{
  "url": "http://minio:9000/org-abc/users/xyz/docs/doc-123/file.pdf?response-content-type=application%2Fpdf&response-content-disposition=inline&X-Amz-Signature=...",
  "expires_in": 3600,
  "document_id": "doc-123",
  "source_type": "collection"
}
```

**Validation:**
- ✅ URL açıldığında PDF tarayıcıda inline görüntülenmeli (indirmemeli)
- ✅ URL 1 saat sonra expire olmalı

### **Test 2: External Source**

**Request:**
```bash
curl -X POST http://localhost:8080/docs/presign \
  -H "Authorization: Bearer {JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "http://external-minio:9000/mevzuat/tuzukler/doc-456/file.pdf",
    "expires_seconds": 3600
  }'
```

**Expected Response:**
```json
{
  "url": "http://external-minio:9000/mevzuat/tuzukler/doc-456/file.pdf?response-content-type=application%2Fpdf&response-content-disposition=inline&X-Amz-Signature=...",
  "expires_in": 3600,
  "document_id": "doc-456",
  "source_type": "external"
}
```

**Validation:**
- ✅ KnowledgeBase Service → Global DB Service'e istek atmalı
- ✅ Global DB Service'ten dönen presigned URL kullanıcıya iletilmeli
- ✅ PDF inline görüntülenmeli

---

## 📁 Dosya Yapısı (KnowledgeBase Service)

```
api/endpoints/documents.py
├── Helper Functions:
│   ├── _is_collection_document(hostname) → bool
│   ├── _extract_minio_path(url) → (bucket, object_key)
│   └── _extract_document_id_from_url(url) → document_id
│
└── POST /docs/presign
    ├── Parse document_url
    ├── Detect source type (collection vs external)
    ├── IF collection:
    │   └── Generate presigned URL directly
    └── ELSE external:
        └── Forward request to Global DB Service

schemas/api/requests/document.py
└── PresignedUrlRequest
    ├── document_url: str
    └── expires_seconds: int

schemas/api/responses/document.py
└── PresignedUrlResponse
    ├── url: str
    ├── expires_in: int
    ├── document_id: str
    └── source_type: str

app/core/auth.py
└── UserContext
    └── raw_token: str  # For external service calls

app/services/global_db_service.py
└── GlobalDBServiceClient
    └── request_presigned_url() → presigned URL from Global DB
```

---

## 🚀 Global DB Service'te Yapılacaklar

1. ✅ Aynı endpoint'i tanımla: `POST /docs/presign`
2. ✅ Request/Response schema'ları oluştur (aynı format)
3. ✅ Helper functions'ları kopyala
4. ✅ MinIO presigned URL generation (inline headers ile)
5. ✅ JWT authentication ekle

**Not**: Global DB Service'te external source detection yapmaya gerek yok, tüm dokümanlar zaten external source.

---

## 📞 İletişim & Sorular

Endpoint implementation sırasında sorun yaşarsanız:
- KnowledgeBase Service implementation'ına bakın: `api/endpoints/documents.py:538-765`
- Helper functions: `api/endpoints/documents.py:465-533`
- Schema definitions: `schemas/api/requests/document.py`, `schemas/api/responses/document.py`

---

**Son Güncelleme**: 2025-10-27
**Versiyon**: 1.0
