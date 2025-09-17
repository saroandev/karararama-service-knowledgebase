"""
Configuration schemas for the application
"""
from schemas.config.app import ApplicationConfig
from schemas.config.milvus import MilvusSettings
from schemas.config.minio import MinIOSettings
from schemas.config.llm import LLMSettings

__all__ = [
    "ApplicationConfig",
    "MilvusSettings",
    "MinIOSettings",
    "LLMSettings",
]

# Create a singleton instance of the application configuration
# This can be imported and used throughout the application
def get_config() -> ApplicationConfig:
    """Get application configuration instance"""
    return ApplicationConfig()

# Convenience function to get specific configurations
def get_milvus_config() -> MilvusSettings:
    """Get Milvus configuration from app config"""
    app_config = get_config()
    return MilvusSettings(
        host=app_config.milvus_host,
        port=app_config.milvus_port,
        collection_name=app_config.milvus_collection,
        dimension=app_config.embedding_dimension
    )

def get_minio_config() -> MinIOSettings:
    """Get MinIO configuration from app config"""
    app_config = get_config()
    return MinIOSettings(
        endpoint=app_config.minio_endpoint,
        access_key=app_config.minio_access_key,
        secret_key=app_config.minio_secret_key,
        secure=app_config.minio_secure,
        bucket_docs=app_config.minio_bucket_docs,
        bucket_chunks=app_config.minio_bucket_chunks
    )

def get_llm_config() -> LLMSettings:
    """Get LLM configuration from app config"""
    app_config = get_config()
    return LLMSettings(
        provider=app_config.llm_provider,
        openai_api_key=app_config.openai_api_key,
        openai_model=app_config.openai_model,
        ollama_model=app_config.ollama_model
    )