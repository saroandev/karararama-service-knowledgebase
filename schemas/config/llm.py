"""
LLM configuration schema
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal, Dict, Any


class LLMSettings(BaseModel):
    """Language Model configuration"""

    # Provider configuration
    provider: Literal["openai", "ollama", "azure", "anthropic"] = Field(
        default="openai",
        description="LLM provider"
    )

    # OpenAI configuration
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    openai_organization: Optional[str] = Field(default=None, description="OpenAI organization ID")
    openai_base_url: Optional[str] = Field(default=None, description="Custom OpenAI API base URL")

    # Ollama configuration
    ollama_model: str = Field(default="qwen2.5:7b-instruct", description="Ollama model name")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")

    # Azure OpenAI configuration
    azure_endpoint: Optional[str] = Field(default=None, description="Azure OpenAI endpoint")
    azure_deployment: Optional[str] = Field(default=None, description="Azure deployment name")
    azure_api_key: Optional[str] = Field(default=None, description="Azure API key")
    azure_api_version: str = Field(default="2024-02-15-preview", description="Azure API version")

    # Model parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for generation")
    max_tokens: int = Field(default=2000, ge=1, description="Maximum tokens to generate")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p sampling")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Presence penalty")
    stop_sequences: Optional[list[str]] = Field(default=None, description="Stop sequences")

    # Retry configuration
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, ge=0, description="Delay between retries")
    timeout: float = Field(default=60.0, ge=1, description="Request timeout in seconds")

    # Advanced settings
    stream: bool = Field(default=False, description="Enable streaming responses")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    response_format: Optional[Dict[str, Any]] = Field(default=None, description="Response format specification")

    @validator("provider")
    def validate_provider_config(cls, v, values):
        """Validate that required fields are present for the selected provider"""
        if v == "openai" and not values.get("openai_api_key"):
            # Will be checked at runtime from environment
            pass
        elif v == "azure" and not all([values.get("azure_endpoint"), values.get("azure_api_key")]):
            # Will be checked at runtime
            pass
        return v

    class Config:
        validate_assignment = True
        extra = "allow"  # Allow extra fields for provider-specific settings