#!/usr/bin/env python3
"""
Docker servisleri bağlantı testi
"""
import sys
import time
sys.path.append('.')

def test_milvus_connection():
    """Milvus bağlantı testi"""
    print("🔌 Milvus bağlantı testi...")
    
    try:
        from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType
        
        # Bağlan
        connections.connect("default", host="localhost", port="19530")
        print("   ✅ Milvus'a bağlandı!")
        
        # Server version
        print(f"   📋 Milvus version: {utility.get_server_version()}")
        
        # Test collection oluştur
        collection_name = "test_rag_chunks"
        
        # Eğer collection varsa sil
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            print(f"   🗑️ Eski collection silindi: {collection_name}")
        
        # Schema tanımla
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, auto_id=True, max_length=100),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8000),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
        ]
        
        schema = CollectionSchema(fields, "RAG chunks collection for testing")
        collection = Collection(collection_name, schema)
        
        print(f"   ✅ Test collection oluşturuldu: {collection_name}")
        
        # Index oluştur
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index("embedding", index_params)
        print("   ✅ Vector index oluşturuldu")
        
        # Load collection
        collection.load()
        print("   ✅ Collection yüklendi")
        
        # Stats
        print(f"   📊 Collection stats: {collection.num_entities} entities")
        
        # Cleanup
        utility.drop_collection(collection_name)
        print("   🧹 Test collection temizlendi")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Milvus bağlantı hatası: {e}")
        return False

def test_minio_connection():
    """MinIO bağlantı testi"""
    print("\n🪣 MinIO bağlantı testi...")
    
    try:
        from minio import Minio
        from minio.error import S3Error
        
        # MinIO client
        client = Minio(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )
        
        # Test bucket names
        docs_bucket = "rag-docs"
        chunks_bucket = "rag-chunks"
        
        print("   ✅ MinIO client oluşturuldu")
        
        # Buckets listele
        buckets = list(client.list_buckets())
        print(f"   📋 Mevcut buckets: {[bucket.name for bucket in buckets]}")
        
        # Test buckets oluştur
        for bucket_name in [docs_bucket, chunks_bucket]:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                print(f"   ✅ Bucket oluşturuldu: {bucket_name}")
            else:
                print(f"   ✅ Bucket zaten var: {bucket_name}")
        
        # Test dosya yükle
        test_content = b"Bu bir test dosyasıdır."
        test_filename = "test_file.txt"
        
        from io import BytesIO
        data = BytesIO(test_content)
        
        client.put_object(
            docs_bucket,
            test_filename,
            data,
            len(test_content),
            content_type="text/plain"
        )
        print(f"   ✅ Test dosya yüklendi: {test_filename}")
        
        # Dosyayı oku
        response = client.get_object(docs_bucket, test_filename)
        content = response.read()
        print(f"   ✅ Test dosya okundu: {len(content)} bytes")
        
        # Temizlik
        client.remove_object(docs_bucket, test_filename)
        print("   🧹 Test dosya silindi")
        
        return True
        
    except Exception as e:
        print(f"   ❌ MinIO bağlantı hatası: {e}")
        return False

def wait_for_services():
    """Servislerin hazır olmasını bekle"""
    print("⏳ Docker servislerin başlatılmasını bekliyorum...")
    
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            # Basit port kontrolü
            import socket
            
            # Milvus port (19530)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            milvus_ready = sock.connect_ex(('localhost', 19530)) == 0
            sock.close()
            
            # MinIO port (9000)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            minio_ready = sock.connect_ex(('localhost', 9000)) == 0
            sock.close()
            
            if milvus_ready and minio_ready:
                print(f"   ✅ Servisler hazır! ({attempt + 1}. deneme)")
                return True
            
            print(f"   ⏳ Bekleniyor... ({attempt + 1}/{max_attempts}) - Milvus: {milvus_ready}, MinIO: {minio_ready}")
            time.sleep(2)
            
        except Exception as e:
            print(f"   ⚠️ Port kontrol hatası: {e}")
            time.sleep(2)
    
    print("   ❌ Servisler hazır olmadı!")
    return False

def main():
    """Ana test fonksiyonu"""
    print("🚀 Docker Servisleri Entegrasyon Testi\n")
    
    # Servislerin hazır olmasını bekle
    if not wait_for_services():
        print("❌ Servisler başlatılamadı. 'docker compose up -d' komutunu çalıştırın.")
        return 1
    
    print("\n" + "="*50)
    
    results = []
    
    # Milvus test
    results.append(("Milvus", test_milvus_connection()))
    
    # MinIO test
    results.append(("MinIO", test_minio_connection()))
    
    # Özet
    print("\n" + "="*50)
    print("📊 DOCKER SERVİSLERİ TEST ÖZETİ")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Geçen testler: {passed}/{total}")
    
    for service, result in results:
        status = "✅ HAZIR" if result else "❌ SORUN"
        print(f"  {service}: {status}")
    
    if passed == total:
        print("\n🎉 Tüm Docker servisleri hazır! Artık RAG pipeline'ını çalıştırabilirsin.")
        print("\nSonraki adım: python integration_test.py")
        return 0
    else:
        print(f"\n⚠️ {total - passed} servis sorunlu. Lütfen docker logs'ları kontrol edin.")
        print("docker compose logs milvus")
        print("docker compose logs minio")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)