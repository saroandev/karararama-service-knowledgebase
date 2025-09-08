# Virtual Environment Migration Guide

## 🎯 Mevcut Durum
Bu proje şu anda Docker container'ları ile çalışıyor. Hem development hem de production için Docker kullanılıyor.

## 🔄 Virtual Environment'a Geçiş

### 1. Virtual Environment Kurulumu

```bash
# Python 3.10 önerilir (Docker'da kullanılan versiyon)
# Mevcut Python versiyonunuz: 3.9.13

# Virtual environment oluştur
python -m venv venv

# Aktif et
source venv/bin/activate  # macOS/Linux
# veya
venv\Scripts\activate  # Windows
```

### 2. Bağımlılıkları Yükle

```bash
# Virtual environment aktifken
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Servisler için Gereksinimler

Virtual environment'da çalıştırmak için aşağıdaki servisleri manuel olarak kurmanız gerekecek:

#### A. Milvus (Vector Database)
```bash
# Docker olmadan Milvus kurulumu zor, Docker kullanmaya devam edebilirsiniz
docker run -d --name milvus-standalone \
  -p 19530:19530 \
  -p 9091:9091 \
  milvusdb/milvus:v2.3.3
```

#### B. MinIO (Object Storage)
```bash
# macOS için
brew install minio/stable/minio

# Linux için
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
sudo mv minio /usr/local/bin/

# Başlat
minio server ~/minio-data --console-address ":9001"
```

#### C. Alternatif: Sadece Servisleri Docker'da Çalıştır
```bash
# Sadece veritabanı servislerini Docker'da çalıştır
docker compose up -d etcd minio milvus attu
```

### 4. Ortam Değişkenleri

`.env` dosyanızı kontrol edin ve gerekli değişkenleri ayarlayın:

```bash
# .env dosyası
OPENAI_API_KEY=sk-your-key-here
MILVUS_HOST=localhost
MILVUS_PORT=19530
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### 5. Uygulamayı Çalıştır

```bash
# Virtual environment aktifken
cd /Users/ugur/Desktop/onedocs-rag

# FastAPI uygulamasını başlat
uvicorn app.server:app --reload --host 0.0.0.0 --port 8080

# Veya production server'ı çalıştır
python production_server.py

# Streamlit arayüzünü başlat (ayrı terminal)
streamlit run streamlit_app.py
```

## 🔧 Development Workflow

### Kod Değişiklikleri
```bash
# Virtual environment'ta kod değişiklikleri otomatik yansır
# --reload flag'i ile uvicorn otomatik restart eder
```

### Test Etme
```bash
# Virtual environment aktifken
python simple_validation.py
python test_system.py
python integration_test.py
```

## ⚠️ Önemli Notlar

1. **Performans**: Docker container'ları izole ortam sağlar, virtual environment'ta sistem kaynaklarını doğrudan kullanırsınız.

2. **Bağımlılık Yönetimi**: Virtual environment'ta farklı Python versiyonları ve paket versiyonları çakışabilir.

3. **Servis Yönetimi**: Docker compose ile tüm servisler tek komutla başlatılır, virtual environment'ta her servisi ayrı yönetmeniz gerekir.

## 🎯 Önerilen Hibrit Yaklaşım

En pratik çözüm, development için hibrit yaklaşım:

```bash
# 1. Veritabanı servislerini Docker'da çalıştır
docker compose up -d etcd minio milvus attu

# 2. Python uygulamasını virtual environment'ta geliştir
source venv/bin/activate
uvicorn app.server:app --reload --host 0.0.0.0 --port 8080
```

Bu yaklaşımın avantajları:
- ✅ Hızlı development cycle
- ✅ Debug kolaylığı
- ✅ Kod değişiklikleri anında yansır
- ✅ Kompleks servisleri Docker'da izole tutarsınız

## 📝 Komut Özeti

```bash
# Virtual environment setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Servisleri başlat (Docker)
docker compose up -d etcd minio milvus attu

# Uygulamayı başlat (Virtual Environment)
uvicorn app.server:app --reload --host 0.0.0.0 --port 8080

# Test et
curl http://localhost:8080/health
```