# MinIO Presigned URL Kullanım Rehberi

> **Diğer servislerde MinIO presigned URL implementasyonu için kapsamlı rehber**
>
> **Oluşturulma Tarihi:** 2025-10-27
> **Proje:** OneDocs RAG Service'den elde edilen bilgilerle

---

## 📚 İçindekiler

1. [Presigned URL Nedir?](#presigned-url-nedir)
2. [Neden Kullanılır?](#neden-kullanılır)
3. [Güvenlik Avantajları](#güvenlik-avantajları)
4. [Implementasyon Adımları](#implementasyon-adımları)
5. [Multi-Tenant Yapı](#multi-tenant-yapı)
6. [Production Deployment](#production-deployment)
7. [Test](#test)
8. [Checklist](#checklist)

---

## Presigned URL Nedir?

MinIO (veya AWS S3) tarafından oluşturulan, **geçici ve güvenli erişim izni** veren URL'lerdir.

### Örnek Karşılaştırma

**❌ Normal MinIO URL (çalışmaz):**
```
http://localhost:9000/bucket-name/path/to/file.pdf
```
Bu URL'e erişmek için MinIO authentication (access key + secret key) gereklidir.

**✅ Presigned URL (çalışır):**
```
http://localhost:9000/bucket-name/path/to/file.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20251027%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20251027T142726Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=391e4a4c904b396c865d2b83aa52ed88748b17fc5ed696f119819b492e84e79e
```

Query parametreleri (`?X-Amz-...`) **authentication token** görevi görür ve:
- ✅ MinIO credentials olmadan erişim sağlar
- ✅ Belirtilen süre sonra (örn: 3600 saniye = 1 saat) expire olur
- ✅ Sadece belirtilen dosyaya erişim verir

---

## Neden Kullanılır?

### Güvenlik ve Kontrol Karşılaştırması

| Yöntem | Frontend'e Credentials Gerekir mi? | Güvenlik Seviyesi | Erişim Kontrolü | Süre Sınırı |
|--------|-------------------------------------|-------------------|-----------------|-------------|
| **Presigned URL** ✅ | ❌ Hayır | 🟢 Yüksek | 🟢 Tam kontrol | 🟢 Var (expire) |
| **Public Bucket** ⚠️ | ❌ Hayır | 🔴 Düşük | 🔴 Yok (herkes erişir) | 🔴 Yok |
| **Direct MinIO Access** ❌ | ✅ Evet (tehlikeli!) | 🔴 Çok düşük | 🔴 Yok | 🔴 Yok |

### Presigned URL Kullanım Senaryoları

1. **Frontend'den Dosya İndirme:** Kullanıcı PDF/Excel gibi dosyayı indirmek istiyor
2. **PDF Viewer:** Frontend'de PDF görüntüleme (iframe, PDF.js, vb.)
3. **Medya Streaming:** Video/Audio oynatma
4. **Geçici Paylaşım:** Dosyayı geçici olarak paylaşma (link 1 saat geçerli)

---

## Güvenlik Avantajları

### ❌ Presigned URL Kullanmadan (Tehlikeli)

```typescript
// Frontend - YANLIŞ YAKLAŞIM
const MINIO_ACCESS_KEY = "minioadmin";  // 🔴 Credentials frontend'de!
const MINIO_SECRET_KEY = "minioadmin";  // 🔴 Herkes görebilir!

// Kullanıcı browser console'da credentials'ları görebilir
// Kötü niyetli kullanıcı tüm MinIO'ya erişebilir!
```

### ✅ Presigned URL Kullanarak (Güvenli)

```typescript
// Frontend - DOĞRU YAKLAŞIM
async function downloadDocument(documentId: string) {
  // 1. Backend'den presigned URL al
  const response = await fetch(`/api/documents/${documentId}`);
  const data = await response.json();

  // 2. Presigned URL'i kullanarak download
  // MinIO credentials gerekmez, URL'de gömülü token var
  const downloadResponse = await fetch(data.document_url);
  const blob = await downloadResponse.blob();

  // 3. Dosyayı indir
  saveAs(blob, data.document_name);
}
```

**Avantajlar:**
- ✅ Frontend hiçbir MinIO credential bilmiyor
- ✅ URL 1 saat sonra otomatik expire oluyor
- ✅ Sadece belirtilen dosyaya erişim var
- ✅ Backend tam kontrol sahibi

---

## Implementasyon Adımları

### Adım 1: MinIO Client Kurulumu

#### 1.1. Package Yükleme

```bash
# Python
pip install minio

# Requirements dosyasına ekle
echo "minio==7.2.0" >> requirements.txt
```

#### 1.2. MinIO Client Sınıfı Oluşturma

```python
# your_service/storage/client.py

import logging
from typing import Optional
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinIOClientManager:
    """MinIO client manager for presigned URL generation"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False
    ):
        """
        Initialize MinIO client

        Args:
            endpoint: MinIO endpoint (örn: "localhost:9000")
            access_key: MinIO access key (örn: "minioadmin")
            secret_key: MinIO secret key (örn: "minioadmin")
            secure: HTTPS kullan mı? (Production: True, Local: False)
        """
        self._client: Optional[Minio] = None
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self._initialize_client()

    def _initialize_client(self):
        """MinIO client'ı başlat"""
        try:
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            logger.info(f"✅ MinIO client initialized: {self.endpoint}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize MinIO client: {e}")
            raise

    def get_client(self) -> Minio:
        """MinIO client'ı döndür"""
        if not self._client:
            self._initialize_client()
        return self._client

    def check_connection(self) -> bool:
        """MinIO bağlantısını kontrol et"""
        try:
            self._client.list_buckets()
            return True
        except Exception as e:
            logger.error(f"❌ MinIO connection failed: {e}")
            return False
```

---

### Adım 2: Presigned URL Generation Fonksiyonu

```python
# your_service/storage/documents.py

from typing import Optional
from datetime import timedelta
from minio import Minio
import logging

logger = logging.getLogger(__name__)


def get_document_presigned_url(
    client: Minio,
    bucket_name: str,
    object_path: str,
    expiry_seconds: int = 3600
) -> Optional[str]:
    """
    MinIO'dan presigned URL oluştur

    Args:
        client: MinIO client instance
        bucket_name: Bucket adı (örn: "my-documents")
        object_path: Object path (örn: "users/user-123/docs/doc-456/file.pdf")
        expiry_seconds: URL geçerlilik süresi (saniye, default: 3600 = 1 saat)

    Returns:
        Presigned URL string veya None (hata durumunda)

    Example:
        >>> client = minio_manager.get_client()
        >>> url = get_document_presigned_url(
        ...     client=client,
        ...     bucket_name="my-documents",
        ...     object_path="users/user-123/docs/doc-456/file.pdf",
        ...     expiry_seconds=3600
        ... )
        >>> print(url)
        "http://localhost:9000/my-documents/users/user-123/docs/doc-456/file.pdf?X-Amz-Algorithm=..."
    """
    try:
        # MinIO presigned GET URL oluştur
        url = client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_path,
            expires=timedelta(seconds=expiry_seconds)
        )

        logger.debug(f"✅ Presigned URL generated: {bucket_name}/{object_path}")
        logger.debug(f"   Expires in: {expiry_seconds} seconds ({expiry_seconds/3600:.1f} hours)")
        return url

    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}")
        logger.error(f"   Bucket: {bucket_name}")
        logger.error(f"   Object: {object_path}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return None


def verify_object_exists(
    client: Minio,
    bucket_name: str,
    object_path: str
) -> bool:
    """
    MinIO'da object'in var olup olmadığını kontrol et

    Args:
        client: MinIO client
        bucket_name: Bucket adı
        object_path: Object path

    Returns:
        True if exists, False otherwise
    """
    try:
        client.stat_object(bucket_name, object_path)
        return True
    except Exception as e:
        logger.warning(f"Object not found: {bucket_name}/{object_path}")
        return False
```

---

### Adım 3: API Endpoint Implementasyonu

```python
# your_service/api/endpoints/documents.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class DocumentURLResponse(BaseModel):
    """Document URL response model"""
    document_id: str
    document_name: str
    document_url: str  # Presigned URL
    url_expires_in_seconds: int
    bucket_name: str
    object_path: str


@router.get("/documents/{document_id}/url", response_model=DocumentURLResponse)
async def get_document_download_url(
    document_id: str,
    expiry_seconds: int = 3600  # Default: 1 saat
):
    """
    Get presigned download URL for a document

    Args:
        document_id: Document ID
        expiry_seconds: URL expiry time in seconds (default: 3600 = 1 hour)

    Returns:
        DocumentURLResponse with presigned URL

    Example Response:
        {
            "document_id": "doc-123",
            "document_name": "contract.pdf",
            "document_url": "http://localhost:9000/my-bucket/docs/doc-123/file.pdf?X-Amz-...",
            "url_expires_in_seconds": 3600,
            "bucket_name": "my-bucket",
            "object_path": "docs/doc-123/file.pdf"
        }
    """
    # 1. MinIO client al
    from your_service.storage.client import minio_client_manager
    client = minio_client_manager.get_client()

    # 2. Bucket ve object path belirle
    bucket_name = "my-documents"  # Kendi bucket adınız
    object_path = f"documents/{document_id}/file.pdf"

    # 3. Dosyanın varlığını kontrol et
    from your_service.storage.documents import verify_object_exists
    if not verify_object_exists(client, bucket_name, object_path):
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found in storage"
        )

    # 4. Presigned URL oluştur
    from your_service.storage.documents import get_document_presigned_url
    presigned_url = get_document_presigned_url(
        client=client,
        bucket_name=bucket_name,
        object_path=object_path,
        expiry_seconds=expiry_seconds
    )

    if not presigned_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate presigned URL"
        )

    # 5. Response döndür
    return DocumentURLResponse(
        document_id=document_id,
        document_name="file.pdf",  # Metadata'dan al
        document_url=presigned_url,
        url_expires_in_seconds=expiry_seconds,
        bucket_name=bucket_name,
        object_path=object_path
    )
```

---

### Adım 4: Environment Variables

```bash
# .env dosyası

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false  # Production'da true

# Presigned URL Settings
PRESIGNED_URL_DEFAULT_EXPIRY=3600  # 1 hour (seconds)
PRESIGNED_URL_MAX_EXPIRY=86400     # 24 hours (max allowed)
```

```python
# your_service/config.py

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # MinIO
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # Presigned URL
    PRESIGNED_URL_DEFAULT_EXPIRY: int = int(os.getenv("PRESIGNED_URL_DEFAULT_EXPIRY", "3600"))
    PRESIGNED_URL_MAX_EXPIRY: int = int(os.getenv("PRESIGNED_URL_MAX_EXPIRY", "86400"))


settings = Settings()
```

---

## Multi-Tenant Yapı

Eğer RAG servisindeki gibi **organization/user scope** yapısı kullanıyorsanız:

### Scope-Aware Presigned URL

```python
# your_service/storage/documents.py

from typing import Optional
from datetime import timedelta
from minio import Minio
import logging

logger = logging.getLogger(__name__)


def get_presigned_url_with_scope(
    client: Minio,
    organization_id: str,
    user_id: Optional[str],
    is_shared: bool,
    document_id: str,
    collection_name: Optional[str] = None,
    expiry_seconds: int = 3600
) -> Optional[str]:
    """
    Multi-tenant yapı için scope-aware presigned URL oluştur

    Args:
        client: MinIO client
        organization_id: Organization ID
        user_id: User ID (private için gerekli, shared için None)
        is_shared: Shared doküman mı?
        document_id: Document ID
        collection_name: Collection adı (opsiyonel)
        expiry_seconds: URL geçerlilik süresi (saniye)

    Returns:
        Presigned URL veya None

    MinIO Folder Structure:
        Private Default: org-{org_id}/users/{user_id}/docs/{doc_id}/file.pdf
        Private Collection: org-{org_id}/users/{user_id}/collections/{collection}/docs/{doc_id}/file.pdf
        Shared Default: org-{org_id}/shared/docs/{doc_id}/file.pdf
        Shared Collection: org-{org_id}/shared/collections/{collection}/docs/{doc_id}/file.pdf

    Example:
        >>> # Private document
        >>> url = get_presigned_url_with_scope(
        ...     client=client,
        ...     organization_id="696e4ef0-9470-4425-ba80-43d94a48a4c1",
        ...     user_id="01bca2a0-2db3-43d6-ad48-cafa8c208921",
        ...     is_shared=False,
        ...     document_id="doc_500b7ba2bea1c48d",
        ...     collection_name="legal-research",
        ...     expiry_seconds=3600
        ... )
        >>> print(url)
        "http://localhost:9000/org-696e4ef0-9470-4425-ba80-43d94a48a4c1/users/01bca2a0-2db3-43d6-ad48-cafa8c208921/collections/legal-research/docs/doc_500b7ba2bea1c48d/file.pdf?X-Amz-..."
    """
    # 1. Bucket name (organization seviyesi)
    bucket_name = f"org-{organization_id}"

    # 2. Object path oluştur
    if is_shared:
        # Shared doküman
        if collection_name:
            object_path = f"shared/collections/{collection_name}/docs/{document_id}/file.pdf"
        else:
            object_path = f"shared/docs/{document_id}/file.pdf"
    else:
        # Private doküman
        if not user_id:
            logger.error("user_id required for private documents")
            return None

        if collection_name:
            object_path = f"users/{user_id}/collections/{collection_name}/docs/{document_id}/file.pdf"
        else:
            object_path = f"users/{user_id}/docs/{document_id}/file.pdf"

    logger.info(f"🔐 Generating scope-aware presigned URL")
    logger.info(f"   Organization: {organization_id}")
    logger.info(f"   User: {user_id if user_id else 'N/A (shared)'}")
    logger.info(f"   Scope: {'Shared' if is_shared else 'Private'}")
    logger.info(f"   Collection: {collection_name if collection_name else 'N/A (default)'}")
    logger.info(f"   Bucket: {bucket_name}")
    logger.info(f"   Object Path: {object_path}")

    # 3. Presigned URL oluştur
    try:
        url = client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_path,
            expires=timedelta(seconds=expiry_seconds)
        )

        logger.info(f"✅ Presigned URL generated successfully")
        logger.debug(f"   URL: {url}")
        return url

    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}")
        logger.error(f"   Bucket: {bucket_name}")
        logger.error(f"   Object: {object_path}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return None
```

### API Endpoint (Multi-Tenant)

```python
# your_service/api/endpoints/documents.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ScopedDocumentURLRequest(BaseModel):
    """Request for scoped document URL"""
    organization_id: str
    user_id: Optional[str] = None  # Required for private, None for shared
    is_shared: bool = False
    collection_name: Optional[str] = None
    expiry_seconds: int = 3600


class ScopedDocumentURLResponse(BaseModel):
    """Response with scoped presigned URL"""
    document_id: str
    document_url: str
    scope: str  # "private" or "shared"
    collection_name: Optional[str] = None
    url_expires_in_seconds: int


@router.post("/documents/{document_id}/scoped-url", response_model=ScopedDocumentURLResponse)
async def get_scoped_document_url(
    document_id: str,
    request: ScopedDocumentURLRequest
):
    """
    Get scope-aware presigned URL for multi-tenant document

    Example Request:
        POST /documents/doc_500b7ba2bea1c48d/scoped-url
        {
            "organization_id": "696e4ef0-9470-4425-ba80-43d94a48a4c1",
            "user_id": "01bca2a0-2db3-43d6-ad48-cafa8c208921",
            "is_shared": false,
            "collection_name": "legal-research",
            "expiry_seconds": 3600
        }
    """
    # 1. MinIO client al
    from your_service.storage.client import minio_client_manager
    client = minio_client_manager.get_client()

    # 2. Scope-aware presigned URL oluştur
    from your_service.storage.documents import get_presigned_url_with_scope

    presigned_url = get_presigned_url_with_scope(
        client=client,
        organization_id=request.organization_id,
        user_id=request.user_id,
        is_shared=request.is_shared,
        document_id=document_id,
        collection_name=request.collection_name,
        expiry_seconds=request.expiry_seconds
    )

    if not presigned_url:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate presigned URL"
        )

    # 3. Response döndür
    return ScopedDocumentURLResponse(
        document_id=document_id,
        document_url=presigned_url,
        scope="shared" if request.is_shared else "private",
        collection_name=request.collection_name,
        url_expires_in_seconds=request.expiry_seconds
    )
```

---

## Production Deployment

### 1. MinIO External Access

#### Docker Compose

```yaml
# docker-compose.yml

version: '3.8'

services:
  minio:
    image: minio/minio:latest
    container_name: minio
    ports:
      - "9000:9000"  # API
      - "9001:9001"  # Console (Web UI)
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  minio_data:
```

#### Kubernetes

```yaml
# minio-deployment.yaml

apiVersion: v1
kind: Service
metadata:
  name: minio
spec:
  type: LoadBalancer
  ports:
    - name: api
      port: 9000
      targetPort: 9000
    - name: console
      port: 9001
      targetPort: 9001
  selector:
    app: minio

---

apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: minio/minio:latest
          args:
            - server
            - /data
            - --console-address
            - ":9001"
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: minio-secret
                  key: root-user
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: minio-secret
                  key: root-password
          ports:
            - containerPort: 9000
            - containerPort: 9001
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: minio-pvc
```

---

### 2. HTTPS ve Domain Kullanımı

Production'da MinIO'yu **reverse proxy** (nginx, Traefik, Caddy) arkasında çalıştırın.

#### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/minio

upstream minio_api {
    server localhost:9000;
}

upstream minio_console {
    server localhost:9001;
}

# API Server (presigned URL için)
server {
    listen 443 ssl http2;
    server_name minio.yourcompany.com;

    ssl_certificate /etc/ssl/certs/minio.crt;
    ssl_certificate_key /etc/ssl/private/minio.key;

    # Allow large file uploads
    client_max_body_size 1000M;

    location / {
        proxy_pass http://minio_api;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Console (Web UI)
server {
    listen 443 ssl http2;
    server_name console.minio.yourcompany.com;

    ssl_certificate /etc/ssl/certs/minio.crt;
    ssl_certificate_key /etc/ssl/private/minio.key;

    location / {
        proxy_pass http://minio_console;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Production Settings

```python
# Production .env

MINIO_ENDPOINT=minio.yourcompany.com  # Domain (HTTPS ile)
MINIO_ACCESS_KEY=your-production-access-key
MINIO_SECRET_KEY=your-production-secret-key
MINIO_SECURE=true  # HTTPS
```

Production presigned URL şöyle görünür:
```
https://minio.yourcompany.com/org-abc123/users/user-xyz/docs/doc-123/file.pdf?X-Amz-Algorithm=...
```

---

### 3. CORS Ayarları

Frontend farklı domain'den MinIO'ya erişecekse **CORS** ayarı gereklidir.

#### MinIO CORS Konfigürasyonu

```bash
# MinIO CLI (mc) kurulumu
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# MinIO'ya bağlan
mc alias set myminio http://localhost:9000 minioadmin minioadmin

# CORS policy dosyası oluştur
cat > cors.json << EOF
{
  "CORSRules": [
    {
      "AllowedOrigins": ["https://yourfrontend.com", "http://localhost:3000"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag", "Content-Length"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

# CORS policy uygula
mc anonymous set-json cors.json myminio/your-bucket-name
```

#### Kubernetes ConfigMap ile CORS

```yaml
# minio-cors-configmap.yaml

apiVersion: v1
kind: ConfigMap
metadata:
  name: minio-cors-config
data:
  cors.json: |
    {
      "CORSRules": [
        {
          "AllowedOrigins": ["https://yourfrontend.com"],
          "AllowedMethods": ["GET", "HEAD"],
          "AllowedHeaders": ["*"],
          "ExposeHeaders": ["ETag"],
          "MaxAgeSeconds": 3000
        }
      ]
    }
```

---

## Test

### Unit Test

```python
# tests/test_presigned_url.py

import pytest
import io
from minio import Minio
from datetime import timedelta


@pytest.fixture
def minio_client():
    """MinIO client fixture"""
    return Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )


@pytest.fixture
def test_bucket(minio_client):
    """Create test bucket"""
    bucket_name = "test-bucket"
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)
    yield bucket_name
    # Cleanup: Remove test bucket (optional)


def test_presigned_url_generation(minio_client, test_bucket):
    """Test presigned URL generation"""
    # 1. Upload test file
    object_path = "test-folder/test-file.pdf"
    test_content = b"Test PDF content"

    minio_client.put_object(
        test_bucket,
        object_path,
        io.BytesIO(test_content),
        len(test_content),
        content_type="application/pdf"
    )

    # 2. Generate presigned URL
    url = minio_client.presigned_get_object(
        test_bucket,
        object_path,
        expires=timedelta(hours=1)
    )

    # 3. Validate URL format
    assert url is not None
    assert url.startswith("http://localhost:9000")
    assert test_bucket in url
    assert "test-folder/test-file.pdf" in url
    assert "X-Amz-Signature" in url
    assert "X-Amz-Algorithm" in url

    # 4. Test URL validity by downloading
    import requests
    response = requests.get(url)
    assert response.status_code == 200
    assert response.content == test_content

    print(f"✅ Presigned URL test passed!")
    print(f"   URL: {url[:100]}...")


def test_presigned_url_expiry(minio_client, test_bucket):
    """Test presigned URL with custom expiry"""
    object_path = "test-folder/expiry-test.pdf"

    # Upload test file
    minio_client.put_object(
        test_bucket,
        object_path,
        io.BytesIO(b"Expiry test"),
        11
    )

    # Generate URL with 10 seconds expiry
    url = minio_client.presigned_get_object(
        test_bucket,
        object_path,
        expires=timedelta(seconds=10)
    )

    assert "X-Amz-Expires=10" in url or "X-Amz-Expires=9" in url  # May vary slightly
    print(f"✅ Expiry test passed!")


def test_presigned_url_nonexistent_file(minio_client, test_bucket):
    """Test presigned URL for non-existent file"""
    # MinIO allows generating presigned URL for non-existent files
    # The URL is valid but returns 404 when accessed

    url = minio_client.presigned_get_object(
        test_bucket,
        "non-existent-file.pdf",
        expires=timedelta(hours=1)
    )

    assert url is not None

    # Try to access non-existent file
    import requests
    response = requests.get(url)
    assert response.status_code == 404

    print(f"✅ Non-existent file test passed!")
```

### Integration Test

```python
# tests/integration/test_api_presigned_url.py

import pytest
from fastapi.testclient import TestClient
from your_service.main import app

client = TestClient(app)


def test_get_document_url_endpoint():
    """Test document URL endpoint"""
    # Assume document exists
    document_id = "test-doc-123"

    response = client.get(f"/api/documents/{document_id}/url")

    assert response.status_code == 200
    data = response.json()

    assert "document_url" in data
    assert "url_expires_in_seconds" in data
    assert data["document_id"] == document_id
    assert "X-Amz-Signature" in data["document_url"]

    print(f"✅ API endpoint test passed!")
    print(f"   Response: {data}")


def test_get_document_url_not_found():
    """Test 404 for non-existent document"""
    response = client.get("/api/documents/non-existent-doc/url")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    print(f"✅ Not found test passed!")
```

### Manual Test Script

```python
# scripts/test_presigned_url.py
"""
Manual test script for presigned URL generation
Run: python scripts/test_presigned_url.py
"""

from minio import Minio
from datetime import timedelta
import requests


def main():
    print("🧪 MinIO Presigned URL Test\n")

    # 1. Connect to MinIO
    print("1️⃣ Connecting to MinIO...")
    client = Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )
    print("   ✅ Connected\n")

    # 2. Check bucket
    bucket_name = "test-bucket"
    print(f"2️⃣ Checking bucket: {bucket_name}")
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"   ✅ Created bucket: {bucket_name}\n")
    else:
        print(f"   ✅ Bucket exists\n")

    # 3. Upload test file
    import io
    object_path = "test/sample.pdf"
    test_content = b"Sample PDF content for testing"

    print(f"3️⃣ Uploading test file: {object_path}")
    client.put_object(
        bucket_name,
        object_path,
        io.BytesIO(test_content),
        len(test_content),
        content_type="application/pdf"
    )
    print(f"   ✅ File uploaded\n")

    # 4. Generate presigned URL
    print(f"4️⃣ Generating presigned URL (1 hour expiry)...")
    url = client.presigned_get_object(
        bucket_name,
        object_path,
        expires=timedelta(hours=1)
    )
    print(f"   ✅ Presigned URL generated:")
    print(f"   {url}\n")

    # 5. Test URL
    print(f"5️⃣ Testing presigned URL...")
    response = requests.get(url)

    if response.status_code == 200:
        print(f"   ✅ URL works! Downloaded {len(response.content)} bytes")
        print(f"   Content matches: {response.content == test_content}")
    else:
        print(f"   ❌ URL failed: {response.status_code}")

    print("\n✅ All tests completed!")


if __name__ == "__main__":
    main()
```

Run test:
```bash
python scripts/test_presigned_url.py
```

---

## Checklist

Diğer servisinde MinIO presigned URL implementasyonu için kontrol listesi:

### Backend Implementation

- [ ] **MinIO client package yükle** (`pip install minio`)
- [ ] **MinIOClientManager sınıfı oluştur** (storage/client.py)
- [ ] **Presigned URL fonksiyonu yaz** (`get_document_presigned_url`)
- [ ] **API endpoint ekle** (`/documents/{id}/url`)
- [ ] **Environment variables tanımla** (MINIO_ENDPOINT, credentials)
- [ ] **Error handling ekle** (file not found, connection errors)
- [ ] **Logging ekle** (debug, info, error levels)

### Multi-Tenant (Opsiyonel)

- [ ] **Scope-aware fonksiyon ekle** (`get_presigned_url_with_scope`)
- [ ] **Organization bucket structure** (org-{org_id}/)
- [ ] **User/Shared separation** (users/{user_id}/ vs shared/)
- [ ] **Collection support** (collections/{name}/docs/)

### Frontend Integration

- [ ] **API client oluştur** (presigned URL almak için)
- [ ] **Download fonksiyonu yaz** (URL ile dosya indirme)
- [ ] **PDF viewer entegrasyonu** (iframe veya PDF.js)
- [ ] **Error handling** (expired URL, 404, etc.)

### Production

- [ ] **HTTPS ayarları** (reverse proxy: nginx/traefik)
- [ ] **Domain konfigürasyonu** (minio.yourcompany.com)
- [ ] **CORS ayarları** (frontend farklı domain'de ise)
- [ ] **Environment variables** (production credentials)
- [ ] **SSL certificates** (Let's Encrypt, etc.)

### Testing

- [ ] **Unit testler yaz** (presigned URL generation)
- [ ] **Integration testler** (API endpoints)
- [ ] **Manual test script** (scripts/test_presigned_url.py)
- [ ] **Load testing** (çok sayıda URL generation)

### Security

- [ ] **MinIO credentials güvenli sakla** (.env, secrets)
- [ ] **URL expiry time belirle** (default: 1 hour)
- [ ] **Frontend'e credentials gönderme** (sadece presigned URL)
- [ ] **HTTPS kullan** (production'da mutlaka)
- [ ] **Access logging** (kim hangi dosyaya erişti)

---

## Özet

### Neler Yapıldı?

1. ✅ **MinIO Presigned URL nedir?** açıklandı
2. ✅ **Neden kullanılır?** (güvenlik, kontrol, expiry)
3. ✅ **Implementasyon adımları** detaylı kod örnekleriyle
4. ✅ **Multi-tenant yapı** (organization/user/shared scopes)
5. ✅ **Production deployment** (Docker, Kubernetes, HTTPS)
6. ✅ **CORS ayarları** (frontend farklı domain için)
7. ✅ **Test stratejileri** (unit, integration, manual)
8. ✅ **Checklist** (adım adım takip için)

### Sonraki Adımlar

Diğer serviste implementasyon yaparken:

1. **Bu rehberi takip et** (adım adım)
2. **Kendi projenize göre uyarla** (bucket names, paths)
3. **Test et** (önce local, sonra production)
4. **Soru olursa sor** (eksik kalan yerler için)

---

**Son Güncelleme:** 2025-10-27
**Kaynak:** OneDocs RAG Service Implementation
**Referans:** `app/core/storage/documents.py:240-315`, `app/core/orchestrator/aggregator.py:117-188`
