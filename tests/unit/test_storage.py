"""
Unit tests for MinIO storage module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
import json
from minio.error import S3Error

from app.storage import MinIOStorage, storage


@pytest.mark.unit
@pytest.mark.storage
class TestMinIOStorage:
    """Test the MinIO storage implementation"""

    @patch('app.storage.Minio')
    def test_minio_storage_initialization(self, mock_minio):
        """Test MinIO storage initialization"""
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage(
            endpoint="localhost:9000",
            access_key="testkey",
            secret_key="testsecret",
            secure=False
        )
        
        assert storage.endpoint == "localhost:9000"
        assert storage.access_key == "testkey"
        assert storage.secure is False
        mock_minio.assert_called_once_with(
            "localhost:9000",
            access_key="testkey",
            secret_key="testsecret", 
            secure=False
        )

    @patch('app.storage.Minio')
    def test_minio_storage_default_secure(self, mock_minio):
        """Test MinIO storage with default secure setting"""
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage(
            endpoint="localhost:9000",
            access_key="testkey",
            secret_key="testsecret"
        )
        
        assert storage.secure is False  # Default value

    @patch('app.storage.Minio')
    def test_create_bucket_success(self, mock_minio):
        """Test successful bucket creation"""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_client.make_bucket.return_value = None
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.create_bucket("test-bucket")
        
        assert result is True
        mock_client.bucket_exists.assert_called_once_with("test-bucket")
        mock_client.make_bucket.assert_called_once_with("test-bucket")

    @patch('app.storage.Minio')
    def test_create_bucket_already_exists(self, mock_minio):
        """Test bucket creation when bucket already exists"""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.create_bucket("existing-bucket")
        
        assert result is True
        mock_client.bucket_exists.assert_called_once_with("existing-bucket")
        mock_client.make_bucket.assert_not_called()

    @patch('app.storage.Minio')
    def test_create_bucket_error(self, mock_minio):
        """Test bucket creation with error"""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_client.make_bucket.side_effect = S3Error("Bucket creation failed", "TestCode", "TestMessage", "TestResource", "TestRequestId", "TestHostId", response=None)
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.create_bucket("error-bucket")
        
        assert result is False

    @patch('app.storage.Minio')
    def test_upload_file_success(self, mock_minio):
        """Test successful file upload"""
        mock_client = MagicMock()
        mock_client.put_object.return_value = MagicMock()
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        file_data = b"test file content"
        
        result = storage.upload_file(
            bucket="test-bucket",
            object_name="test-file.txt",
            file_data=file_data,
            content_type="text/plain"
        )
        
        assert result is True
        mock_client.put_object.assert_called_once()
        
        # Check the call arguments
        call_args = mock_client.put_object.call_args
        assert call_args[0][0] == "test-bucket"
        assert call_args[0][1] == "test-file.txt"
        assert call_args[1]["content_type"] == "text/plain"

    @patch('app.storage.Minio')
    def test_upload_file_with_metadata(self, mock_minio):
        """Test file upload with metadata"""
        mock_client = MagicMock()
        mock_client.put_object.return_value = MagicMock()
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        file_data = b"test content"
        metadata = {"author": "test", "version": "1.0"}
        
        result = storage.upload_file(
            bucket="test-bucket",
            object_name="test-file.txt", 
            file_data=file_data,
            metadata=metadata
        )
        
        assert result is True
        call_args = mock_client.put_object.call_args
        assert call_args[1]["metadata"] == metadata

    @patch('app.storage.Minio')
    def test_upload_file_error(self, mock_minio):
        """Test file upload with error"""
        mock_client = MagicMock()
        mock_client.put_object.side_effect = S3Error("Upload failed", "TestCode", "TestMessage", "TestResource", "TestRequestId", "TestHostId", response=None)
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        file_data = b"test content"
        
        result = storage.upload_file("test-bucket", "test-file.txt", file_data)
        
        assert result is False

    @patch('app.storage.Minio')
    def test_download_file_success(self, mock_minio):
        """Test successful file download"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"downloaded content"
        mock_client.get_object.return_value = mock_response
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.download_file("test-bucket", "test-file.txt")
        
        assert result == b"downloaded content"
        mock_client.get_object.assert_called_once_with("test-bucket", "test-file.txt")
        mock_response.read.assert_called_once()

    @patch('app.storage.Minio')
    def test_download_file_not_found(self, mock_minio):
        """Test file download when file not found"""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = S3Error("Object not found", "NoSuchKey", "The specified key does not exist", "TestResource", "TestRequestId", "TestHostId", response=None)
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.download_file("test-bucket", "nonexistent-file.txt")
        
        assert result is None

    @patch('app.storage.Minio')
    def test_delete_file_success(self, mock_minio):
        """Test successful file deletion"""
        mock_client = MagicMock()
        mock_client.remove_object.return_value = None
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.delete_file("test-bucket", "test-file.txt")
        
        assert result is True
        mock_client.remove_object.assert_called_once_with("test-bucket", "test-file.txt")

    @patch('app.storage.Minio')
    def test_delete_file_error(self, mock_minio):
        """Test file deletion with error"""
        mock_client = MagicMock()
        mock_client.remove_object.side_effect = S3Error("Delete failed", "TestCode", "TestMessage", "TestResource", "TestRequestId", "TestHostId", response=None)
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.delete_file("test-bucket", "test-file.txt")
        
        assert result is False

    @patch('app.storage.Minio')
    def test_list_files_success(self, mock_minio):
        """Test successful file listing"""
        mock_client = MagicMock()
        mock_objects = [
            MagicMock(object_name="file1.txt", size=100, last_modified="2024-01-01"),
            MagicMock(object_name="file2.txt", size=200, last_modified="2024-01-02")
        ]
        mock_client.list_objects.return_value = mock_objects
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.list_files("test-bucket")
        
        assert len(result) == 2
        assert result[0]["name"] == "file1.txt"
        assert result[0]["size"] == 100
        assert result[1]["name"] == "file2.txt"
        assert result[1]["size"] == 200
        
        mock_client.list_objects.assert_called_once_with("test-bucket", prefix=None)

    @patch('app.storage.Minio')
    def test_list_files_with_prefix(self, mock_minio):
        """Test file listing with prefix filter"""
        mock_client = MagicMock()
        mock_objects = [
            MagicMock(object_name="docs/file1.txt", size=100, last_modified="2024-01-01")
        ]
        mock_client.list_objects.return_value = mock_objects
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.list_files("test-bucket", prefix="docs/")
        
        assert len(result) == 1
        assert result[0]["name"] == "docs/file1.txt"
        mock_client.list_objects.assert_called_once_with("test-bucket", prefix="docs/")

    @patch('app.storage.Minio')
    def test_list_files_empty_bucket(self, mock_minio):
        """Test file listing on empty bucket"""
        mock_client = MagicMock()
        mock_client.list_objects.return_value = []
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.list_files("empty-bucket")
        
        assert result == []

    @patch('app.storage.Minio')
    def test_file_exists_true(self, mock_minio):
        """Test file existence check - file exists"""
        mock_client = MagicMock()
        mock_client.stat_object.return_value = MagicMock()
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.file_exists("test-bucket", "existing-file.txt")
        
        assert result is True
        mock_client.stat_object.assert_called_once_with("test-bucket", "existing-file.txt")

    @patch('app.storage.Minio')
    def test_file_exists_false(self, mock_minio):
        """Test file existence check - file does not exist"""
        mock_client = MagicMock()
        mock_client.stat_object.side_effect = S3Error("Object not found", "NoSuchKey", "The specified key does not exist", "TestResource", "TestRequestId", "TestHostId", response=None)
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.file_exists("test-bucket", "nonexistent-file.txt")
        
        assert result is False

    @patch('app.storage.Minio')
    def test_get_file_info_success(self, mock_minio):
        """Test getting file information"""
        mock_client = MagicMock()
        mock_stat = MagicMock()
        mock_stat.size = 1024
        mock_stat.last_modified = "2024-01-01T12:00:00Z"
        mock_stat.content_type = "text/plain"
        mock_stat.metadata = {"author": "test"}
        mock_client.stat_object.return_value = mock_stat
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.get_file_info("test-bucket", "test-file.txt")
        
        assert result["size"] == 1024
        assert result["last_modified"] == "2024-01-01T12:00:00Z"
        assert result["content_type"] == "text/plain"
        assert result["metadata"] == {"author": "test"}

    @patch('app.storage.Minio')
    def test_get_file_info_not_found(self, mock_minio):
        """Test getting file information for nonexistent file"""
        mock_client = MagicMock()
        mock_client.stat_object.side_effect = S3Error("Object not found", "NoSuchKey", "The specified key does not exist", "TestResource", "TestRequestId", "TestHostId", response=None)
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.get_file_info("test-bucket", "nonexistent-file.txt")
        
        assert result is None

    @patch('app.storage.Minio')
    def test_upload_json_data(self, mock_minio):
        """Test uploading JSON data"""
        mock_client = MagicMock()
        mock_client.put_object.return_value = MagicMock()
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        data = {"key": "value", "number": 42}
        
        result = storage.upload_json("test-bucket", "data.json", data)
        
        assert result is True
        # Verify JSON serialization
        call_args = mock_client.put_object.call_args
        assert call_args[1]["content_type"] == "application/json"

    @patch('app.storage.Minio')
    def test_download_json_data(self, mock_minio):
        """Test downloading JSON data"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        json_data = {"key": "value", "number": 42}
        mock_response.read.return_value = json.dumps(json_data).encode('utf-8')
        mock_client.get_object.return_value = mock_response
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.download_json("test-bucket", "data.json")
        
        assert result == json_data

    @patch('app.storage.Minio')
    def test_download_invalid_json(self, mock_minio):
        """Test downloading invalid JSON data"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json content"
        mock_client.get_object.return_value = mock_response
        mock_minio.return_value = mock_client
        
        storage = MinIOStorage("localhost:9000", "key", "secret")
        result = storage.download_json("test-bucket", "invalid.json")
        
        assert result is None


@pytest.mark.unit
@pytest.mark.storage
class TestStorageSingleton:
    """Test the storage singleton instance"""

    @patch('app.config.settings')
    @patch('app.storage.MinIOStorage')
    def test_storage_singleton_creation(self, mock_storage_class, mock_settings):
        """Test storage singleton is created with correct settings"""
        mock_settings.MINIO_ENDPOINT = "test:9000"
        mock_settings.MINIO_ROOT_USER = "testkey"
        mock_settings.MINIO_ROOT_PASSWORD = "testsecret"
        mock_settings.MINIO_SECURE = True
        
        mock_instance = MagicMock()
        mock_storage_class.return_value = mock_instance
        
        from app.storage import storage
        
        # The singleton should be created with settings
        mock_storage_class.assert_called_once_with(
            endpoint="test:9000",
            access_key="testkey",
            secret_key="testsecret", 
            secure=True
        )


@pytest.mark.integration
@pytest.mark.storage
@pytest.mark.requires_docker
class TestMinIOStorageIntegration:
    """Integration tests for MinIO storage (requires Docker)"""

    @pytest.mark.slow
    def test_full_storage_workflow(self, docker_services_available):
        """Test complete storage workflow with real MinIO"""
        if not docker_services_available["minio"]:
            pytest.skip("MinIO service not available")
        
        from app.storage import storage
        
        # Test bucket creation
        bucket_name = "test-integration-bucket"
        assert storage.create_bucket(bucket_name)
        
        # Test file upload
        test_data = b"Integration test content"
        assert storage.upload_file(bucket_name, "test-file.txt", test_data)
        
        # Test file existence
        assert storage.file_exists(bucket_name, "test-file.txt")
        
        # Test file download
        downloaded = storage.download_file(bucket_name, "test-file.txt")
        assert downloaded == test_data
        
        # Test file listing
        files = storage.list_files(bucket_name)
        assert len(files) >= 1
        assert any(f["name"] == "test-file.txt" for f in files)
        
        # Test file deletion
        assert storage.delete_file(bucket_name, "test-file.txt")
        assert not storage.file_exists(bucket_name, "test-file.txt")

    def test_json_storage_workflow(self, docker_services_available):
        """Test JSON storage workflow"""
        if not docker_services_available["minio"]:
            pytest.skip("MinIO service not available")
            
        from app.storage import storage
        
        bucket_name = "test-json-bucket"
        storage.create_bucket(bucket_name)
        
        # Test JSON upload/download
        test_data = {"test": True, "value": 123, "array": [1, 2, 3]}
        
        assert storage.upload_json(bucket_name, "test-data.json", test_data)
        downloaded_data = storage.download_json(bucket_name, "test-data.json")
        
        assert downloaded_data == test_data
        
        # Cleanup
        storage.delete_file(bucket_name, "test-data.json")