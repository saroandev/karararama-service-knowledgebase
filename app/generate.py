"""
Backward compatibility module for LLM generation.

This file is kept for backward compatibility.
All imports from 'app.generate' will be redirected to the new package structure.
New code should use 'from app.core.generation import ...' directly.
"""
import logging
import warnings
from typing import List, Dict, Any, Optional, Generator

# Import from new location
from app.core.generation import (
    AbstractGenerator,
    OpenAIGenerator,
    OllamaGenerator,
    create_generator,
    default_generator
)
from app.config import settings

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "Importing from app.generate is deprecated. Use app.core.generation instead.",
    DeprecationWarning,
    stacklevel=2
)


# Legacy LLMGenerator class for backward compatibility
class LLMGenerator:
    """
    Legacy LLMGenerator class for backward compatibility.
    This wraps the new generator implementations.
    """

    def __init__(self):
        """Initialize LLM generator"""
        warnings.warn(
            "LLMGenerator is deprecated. Use OpenAIGenerator or OllamaGenerator from app.core.generation",
            DeprecationWarning,
            stacklevel=2
        )

        self.provider = settings.LLM_PROVIDER or 'openai'

        # Create the appropriate generator
        try:
            self._impl = create_generator(provider=self.provider)
            self.model = self._impl.model_name
            self.client = getattr(self._impl, 'client', None)

            if self.provider == "ollama":
                self.ollama_url = getattr(self._impl, 'base_url', "http://localhost:11434")
        except Exception as e:
            logger.error(f"Failed to initialize generator: {e}")
            raise

        logger.info(f"Initialized {self.provider} LLM client with model: {self.model}")

    def setup_client(self):
        """Legacy method - no longer needed"""
        pass

    def generate_answer(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """Generate answer from context chunks"""
        return self._impl.generate_answer(
            question, context_chunks, max_tokens, temperature, include_sources
        )

    def generate_streaming(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> Generator[str, None, None]:
        """Generate streaming response"""
        return self._impl.generate_streaming(
            question, context_chunks, max_tokens, temperature
        )

    def summarize_document(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """Generate a summary of document chunks"""
        if hasattr(self._impl, 'summarize_document'):
            return self._impl.summarize_document(chunks, max_tokens)

        # Fallback implementation
        full_text = "\n\n".join([chunk.get("text", "") for chunk in chunks])
        if len(full_text) > 10000:
            full_text = full_text[:10000] + "..."

        prompt = f"""Aşağıdaki dokümanın özetini çıkar. Önemli noktaları vurgula ve ana konuları listele.

Dokümant:
{full_text}

Özet:"""

        response = self._impl.generate_answer(
            "Özet oluştur",
            [{"text": full_text}],
            max_tokens,
            0.3,
            False
        )

        return {
            "summary": response["answer"],
            "metadata": response["metadata"]
        }

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string from chunks"""
        return self._impl.build_context(chunks)

    def _create_prompt(
        self,
        question: str,
        context: str,
        include_sources: bool
    ) -> str:
        """Create the prompt for the LLM"""
        return self._impl.create_prompt(question, context, include_sources)

    def _extract_sources(
        self,
        answer: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract source references from the answer"""
        # Add storage lookup for backward compatibility
        from app.storage import storage
        sources = self._impl.extract_sources(answer, chunks)

        # Enhance sources with document metadata and URLs
        doc_metadata_cache = {}

        for source in sources:
            doc_id = source.get("document_id", "unknown")

            # Get document metadata if not cached
            if doc_id not in doc_metadata_cache and doc_id != "unknown":
                try:
                    doc_metadata_cache[doc_id] = storage.get_document_metadata(doc_id)
                except:
                    doc_metadata_cache[doc_id] = None

            # Get the original filename from metadata
            original_filename = "unknown.pdf"
            if doc_id in doc_metadata_cache and doc_metadata_cache[doc_id]:
                original_filename = doc_metadata_cache[doc_id].get("original_filename", f"{doc_id}.pdf")

            # Add document name and URL
            source["document_name"] = original_filename
            source["document_url"] = f"http://localhost:9001/browser/raw-documents/{doc_id}/{original_filename}"

        return sources

    def _format_response(
        self,
        response: Dict[str, Any],
        chunks: List[Dict[str, Any]],
        include_sources: bool
    ) -> Dict[str, Any]:
        """Format the final response with metadata"""
        return self._impl.format_response(response, chunks, include_sources)

    # Legacy method delegates for compatibility
    def _generate_openai(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Legacy OpenAI generation method"""
        if isinstance(self._impl, OpenAIGenerator):
            return self._impl._generate_completion(prompt, max_tokens, temperature)
        raise NotImplementedError("Not using OpenAI provider")

    def _generate_ollama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Legacy Ollama generation method"""
        if isinstance(self._impl, OllamaGenerator):
            import asyncio
            return asyncio.run(
                self._impl._generate_completion_async(prompt, max_tokens, temperature)
            )
        raise NotImplementedError("Not using Ollama provider")

    async def _generate_ollama_async(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Legacy async Ollama generation method"""
        if isinstance(self._impl, OllamaGenerator):
            return await self._impl._generate_completion_async(prompt, max_tokens, temperature)
        raise NotImplementedError("Not using Ollama provider")


# Create singleton instance for backward compatibility
llm_generator = LLMGenerator() if default_generator else None


# Export everything for backward compatibility
__all__ = [
    'LLMGenerator',
    'llm_generator',
    # Also export new names
    'AbstractGenerator',
    'OpenAIGenerator',
    'OllamaGenerator',
    'create_generator',
    'default_generator'
]