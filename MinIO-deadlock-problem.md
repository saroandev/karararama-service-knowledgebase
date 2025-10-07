# MinIO Deadlock Problemi - Çözüm Raporu

## Tarih: 2025-10-07

## Problem Tanımı

Document upload işlemi sırasında MinIO'da sürekli olarak aşağıdaki hata alınıyordu:

```
S3 operation failed; code: InternalError,
message: We encountered an internal error, please try again.:
cause(resource deadlock avoided)
```

### Hata Detayları

```python
resource: /org-696e4ef0-9470-4425-ba80-43d94a48a4c1/users/user-17d0faab-0830-4007-8ed6-73cfd049505b/docs/doc_a76164c5d47b9669/disisleri_teskilatini_guclendirme_vakfi_kanunu_7512.pdf
bucket_name: org-696e4ef0-9470-4425-ba80-43d94a48a4c1
object_name: users/user-17d0faab-0830-4007-8ed6-73cfd049505b/docs/doc_a76164c5d47b9669/disisleri_teskilatini_guclendirme_vakfi_kanunu_7512.pdf
```

## Kök Neden Analizi

### 1. MinIO Internal State Problemi

Docker logs incelendiğinde, MinIO'nun **temp dosyadan final path'e rename** yaparken internal deadlock oluştuğu görüldü:

```
Error: drive:/data,
srcVolume: .minio.sys/tmp,
srcPath: bdb0b6b5-4504-4dbf-9bfc-064a002753a6,
dstVolume: org-696e4ef0-9470-4425-ba80-43d94a48a4c1:,
dstPath: users/user-17d0faab-0830-4007-8ed6-73cfd049505b/docs/doc_a76164c5d47b9669/disisleri_teskilatini_guclendirme_vakfi_kanunu_7512.pdf
- error resource deadlock avoided (*errors.errorString)
```

**Açıklama**:
- MinIO upload işleminde önce `.minio.sys/tmp/` altına geçici dosya yazar
- Sonra bu dosyayı target path'e rename/move eder
- Bu işlem sırasında file lock mekanizması deadlock'a girmiş

### 2. Client-Side Denemeler (İşe Yaramadı)

Başlangıçta sorunun client-side connection pool yönetiminden kaynaklandığı düşünüldü ve şu değişiklikler yapıldı:

#### a) Fresh Client Oluşturma (❌ Çözmedi)
```python
# Her upload için yeni client
client = self.client_manager.create_fresh_client()
```
**Sonuç**: Resource leak'e sebep oldu, sorun daha da kötüleşti çünkü her yeni client yeni bir PoolManager yaratıyordu ve eski pool'lar kapatılmıyordu.

#### b) Connection Pool Optimizasyonu (❌ Tek başına yetmedi)
```python
http_client = urllib3.PoolManager(
    timeout=urllib3.Timeout(connect=30.0, read=300.0),
    maxsize=50,  # 100'den 50'ye düşürüldü
    block=False,  # Non-blocking mode
    retries=urllib3.Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[502, 503, 504]
    )
)
```
**Sonuç**: İyileştirme sağladı ama sorun devam etti.

#### c) Retry Logic Kaldırma (❌ Yeterli olmadı)
Upload fonksiyonundaki manuel retry loop kaldırıldı (HTTP client zaten retry yapıyor).

### 3. Asıl Çözüm: MinIO Container Restart

**Çözüm**:
```bash
docker restart milvus-minio
```

**Neden İşe Yaradı**:
- MinIO'nun internal state'i bozulmuştu
- File lock mekanizması deadlock'a girmişti
- Temp directory'deki orphan lock'lar temizlenmemişti
- Container restart ile tüm internal state sıfırlandı

## Denenen Path Optimizasyonları

### İlk Yapı (Deadlock sırasında)
```
org-{org_id}/users/user-{user_id}/docs/{doc_id}/{filename}.pdf
```

### Geçici Basitleştirme (Test amaçlı)
```
{user_id}/docs/{doc_id}/{filename}.pdf
```
**Sonuç**: MinIO restart sonrası bu da çalıştı.

### Final Yapı (Kullanıcı tercihi)
```
org-{org_id}/users/{user_id}/docs/{doc_id}/{filename}.pdf
```
**Sonuç**: MinIO restart sonrası sorunsuz çalıştı.

**Önemli Not**: Path derinliği sorun değildi! MinIO'nun internal state'i sorundu.

## Çözüm Adımları

1. **MinIO container'ı restart et**:
   ```bash
   docker restart milvus-minio
   ```

2. **Client-side optimizasyonları koru**:
   - Paylaşımlı client kullan (`get_client()`)
   - Her upload için yeni client yaratma (resource leak)
   - Non-blocking pool manager (`block=False`)
   - Makul pool size (50)

3. **Python cache temizle**:
   ```bash
   find . -type d -name "__pycache__" -exec rm -rf {} +
   find . -type f -name "*.pyc" -delete
   ```

4. **API server restart**:
   ```bash
   pkill -f uvicorn
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8080
   ```

## Kod Değişiklikleri (Final)

### 1. MinIO Client Manager (`app/core/storage/client.py`)

```python
def _initialize_client(self):
    """Initialize MinIO client with custom HTTP settings"""
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=30.0, read=300.0),
        maxsize=50,  # Reduced pool size
        block=False,  # Non-blocking mode to prevent deadlock
        retries=urllib3.Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504]
        )
    )

    self._client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        http_client=http_client
    )
```

### 2. Document Storage (`app/core/storage/documents.py`)

```python
# Paylaşımlı client kullan
client = self.client_manager.get_client()

# Bucket'i scope ile oluştur
if scope:
    raw_bucket = scope.get_bucket_name()
    object_prefix = scope.get_object_prefix("docs")
    self.client_manager.ensure_scope_bucket(scope)

# Direct upload (retry yok)
file_stream = io.BytesIO(file_data)
client.put_object(
    raw_bucket,
    pdf_object_name,
    file_stream,
    len(file_data),
    content_type="application/pdf"
)
```

### 3. Scope Path Generator (`schemas/api/requests/scope.py`)

```python
def get_object_prefix(self, category: str = "docs") -> str:
    """
    Generate MinIO object prefix (folder path) for this scope

    Folder structure:
    - PRIVATE: users/{user_id}/{category}/
    - SHARED: shared/{category}/
    """
    if self.scope_type == DataScope.PRIVATE:
        return f"users/{self.user_id}/{category}/"
    elif self.scope_type == DataScope.SHARED:
        return f"shared/{category}/"
```

## Gelecek İçin Önlemler

### 1. Health Check
MinIO health check ekle:
```python
def check_minio_health(self) -> bool:
    try:
        self._client.list_buckets()
        return True
    except Exception as e:
        logger.error(f"MinIO health check failed: {e}")
        return False
```

### 2. Monitoring
MinIO logs'u izle:
```bash
docker logs milvus-minio -f | grep -i "error\|deadlock"
```

### 3. Graceful Degradation
Upload fail olursa retry mekanizması ekle (ama API level'da, storage layer'da değil):
```python
max_retries = 3
for attempt in range(max_retries):
    if storage.upload_document(...):
        break
    else:
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff
```

### 4. Container Maintenance
MinIO container'ı periyodik olarak restart et (örn: haftada bir):
```bash
# Crontab
0 2 * * 0 docker restart milvus-minio
```

## Öğrenilen Dersler

1. **Client-side optimizasyonlar her zaman yeterli değil**: Bazen problem server-side'dadır.

2. **Resource leak'e dikkat**: Her request için yeni client/pool yaratmak sorunlu.

3. **MinIO internal state**: Long-running MinIO instance'ları bazen internal deadlock'a girebilir.

4. **Path derinliği sorun değil**: `users/{user_id}/docs/` vs `{user_id}/docs/` fark etmez.

5. **Container restart en basit çözüm**: Karmaşık client-side fix'ler yerine bazen basit bir restart yeterli.

6. **Logs çok önemli**: Docker logs olmadan root cause'u bulmak çok zordu.

## Referanslar

- [MinIO Deadlock Issues](https://github.com/minio/minio/issues?q=deadlock)
- [urllib3 PoolManager](https://urllib3.readthedocs.io/en/stable/reference/urllib3.poolmanager.html)
- [MinIO Python Client](https://min.io/docs/minio/linux/developers/python/API.html)

---

**Son Durum**: ✅ Problem çözüldü. MinIO restart + optimized client configuration ile sorun tamamen giderildi.
