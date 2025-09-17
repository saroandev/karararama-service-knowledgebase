"""
Generation package for LLM text generation

This package provides multiple LLM generation implementations:
- OpenAI (GPT-4, GPT-3.5)
- Ollama (local models)
"""
import logging
from typing import Optional

from app.core.generation.base import AbstractGenerator
from app.core.generation.openai_generator import OpenAIGenerator
from app.core.generation.ollama_generator import OllamaGenerator
from app.config import settings

logger = logging.getLogger(__name__)


def create_generator(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    **kwargs
) -> AbstractGenerator:
    """
    Factory function to create LLM generator based on provider

    Args:
        provider: LLM provider ('openai' or 'ollama')
        model_name: Model name to use
        **kwargs: Additional arguments for the specific implementation

    Returns:
        LLM generator instance
    """
    provider = provider or settings.LLM_PROVIDER or 'openai'

    if provider.lower() == 'openai':
        logger.info("Creating OpenAI generator")
        return OpenAIGenerator(
            model_name=model_name,
            **kwargs
        )
    elif provider.lower() == 'ollama':
        logger.info("Creating Ollama generator")
        return OllamaGenerator(
            model_name=model_name,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# Create default generator instance
# Using OpenAI by default as it's more reliable
try:
    default_generator = create_generator(provider='openai')
    logger.info("Default LLM generator initialized with OpenAI")
except Exception as e:
    logger.warning(f"Failed to initialize default generator with OpenAI: {e}")
    # Try Ollama as fallback
    try:
        default_generator = create_generator(provider='ollama')
        logger.info("Default LLM generator initialized with Ollama as fallback")
    except Exception as e2:
        logger.error(f"Failed to initialize any LLM generator: {e2}")
        default_generator = None


# Export all classes and functions
__all__ = [
    'AbstractGenerator',
    'OpenAIGenerator',
    'OllamaGenerator',
    'create_generator',
    'default_generator'
]