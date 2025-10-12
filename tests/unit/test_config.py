"""
Unit tests for configuration module
"""
import pytest
import os
from unittest.mock import patch
from app.config import Settings, settings


@pytest.mark.unit
class TestSettings:
    """Test the Settings class"""

    def test_default_values(self):
        """Test default configuration values"""
        config = Settings()

        assert config.MILVUS_HOST == "localhost"
        assert config.MILVUS_PORT == 19530
        assert config.MILVUS_COLLECTION == "rag_chunks"  # Legacy default (backward compatibility)
        
        assert config.MINIO_ENDPOINT == "localhost:9000"
        assert config.MINIO_ROOT_USER == "minioadmin"
        assert config.MINIO_ROOT_PASSWORD == "minioadmin"
        assert config.MINIO_SECURE is False
        assert config.MINIO_BUCKET_DOCS == "rag-docs"
        assert config.MINIO_BUCKET_CHUNKS == "rag-chunks"
        
        assert config.EMBEDDING_MODEL == "intfloat/multilingual-e5-small"
        assert config.RERANKER_MODEL == "BAAI/bge-reranker-v2-m3"
        
        assert config.LLM_PROVIDER == "ollama"
        assert config.OLLAMA_MODEL == "qwen2.5:7b-instruct"

    @patch.dict(os.environ, {
        "MILVUS_HOST": "test-milvus",
        "MILVUS_PORT": "19531",
        "MILVUS_COLLECTION": "test_collection",
        "MINIO_ENDPOINT": "test-minio:9001",
        "MINIO_SECURE": "true",
        "EMBEDDING_MODEL": "test-model",
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "test-key-123"
    })
    def test_environment_variables(self):
        """Test configuration from environment variables"""
        config = Settings()
        
        assert config.MILVUS_HOST == "test-milvus"
        assert config.MILVUS_PORT == 19531
        assert config.MILVUS_COLLECTION == "test_collection"  # Legacy setting for test
        
        assert config.MINIO_ENDPOINT == "test-minio:9001"
        assert config.MINIO_SECURE is True
        
        assert config.EMBEDDING_MODEL == "test-model"
        assert config.LLM_PROVIDER == "openai"
        assert config.OPENAI_API_KEY == "test-key-123"

    def test_boolean_conversion(self):
        """Test boolean environment variable conversion"""
        # Test various true values
        with patch.dict(os.environ, {"MINIO_SECURE": "true"}):
            assert Settings().MINIO_SECURE is True
            
        with patch.dict(os.environ, {"MINIO_SECURE": "True"}):
            assert Settings().MINIO_SECURE is True
            
        with patch.dict(os.environ, {"MINIO_SECURE": "TRUE"}):
            assert Settings().MINIO_SECURE is True
        
        # Test false values
        with patch.dict(os.environ, {"MINIO_SECURE": "false"}):
            assert Settings().MINIO_SECURE is False
            
        with patch.dict(os.environ, {"MINIO_SECURE": "0"}):
            assert Settings().MINIO_SECURE is False
            
        with patch.dict(os.environ, {"MINIO_SECURE": ""}):
            assert Settings().MINIO_SECURE is False

    def test_integer_conversion(self):
        """Test integer environment variable conversion"""
        with patch.dict(os.environ, {"MILVUS_PORT": "12345"}):
            assert Settings().MILVUS_PORT == 12345
        
        # Test invalid integer
        with patch.dict(os.environ, {"MILVUS_PORT": "invalid"}):
            with pytest.raises(ValueError):
                Settings()

    def test_singleton_settings(self):
        """Test that settings is a singleton instance"""
        from app.config import settings
        assert isinstance(settings, Settings)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"})
    def test_openai_key_presence(self):
        """Test OpenAI API key detection"""
        config = Settings()
        assert config.OPENAI_API_KEY == "sk-test123"

    def test_missing_openai_key(self):
        """Test handling of missing OpenAI API key"""
        with patch.dict(os.environ, {}, clear=True):
            config = Settings()
            assert config.OPENAI_API_KEY is None

    def test_all_required_attributes(self):
        """Test that all expected attributes are present"""
        config = Settings()
        
        # Milvus attributes
        assert hasattr(config, "MILVUS_HOST")
        assert hasattr(config, "MILVUS_PORT")
        assert hasattr(config, "MILVUS_COLLECTION")  # Legacy attribute (backward compatibility)
        
        # MinIO attributes
        assert hasattr(config, "MINIO_ENDPOINT")
        assert hasattr(config, "MINIO_ROOT_USER")
        assert hasattr(config, "MINIO_ROOT_PASSWORD")
        assert hasattr(config, "MINIO_SECURE")
        assert hasattr(config, "MINIO_BUCKET_DOCS")
        assert hasattr(config, "MINIO_BUCKET_CHUNKS")
        
        # Model attributes
        assert hasattr(config, "EMBEDDING_MODEL")
        assert hasattr(config, "RERANKER_MODEL")
        
        # LLM attributes
        assert hasattr(config, "LLM_PROVIDER")
        assert hasattr(config, "OLLAMA_MODEL")
        assert hasattr(config, "OPENAI_API_KEY")

    def test_config_types(self):
        """Test that configuration values have correct types"""
        config = Settings()
        
        assert isinstance(config.MILVUS_HOST, str)
        assert isinstance(config.MILVUS_PORT, int)
        assert isinstance(config.MILVUS_COLLECTION, str)  # Legacy setting
        
        assert isinstance(config.MINIO_ENDPOINT, str)
        assert isinstance(config.MINIO_ROOT_USER, str)
        assert isinstance(config.MINIO_ROOT_PASSWORD, str)
        assert isinstance(config.MINIO_SECURE, bool)
        assert isinstance(config.MINIO_BUCKET_DOCS, str)
        assert isinstance(config.MINIO_BUCKET_CHUNKS, str)
        
        assert isinstance(config.EMBEDDING_MODEL, str)
        assert isinstance(config.RERANKER_MODEL, str)
        assert isinstance(config.LLM_PROVIDER, str)
        assert isinstance(config.OLLAMA_MODEL, str)

    @patch.dict(os.environ, {
        "MINIO_ENDPOINT": "custom:8080",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
    })
    def test_custom_configuration(self):
        """Test custom configuration scenarios"""
        config = Settings()
        
        assert config.MINIO_ENDPOINT == "custom:8080"
        assert config.EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"