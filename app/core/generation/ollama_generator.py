"""
Ollama LLM generator implementation
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Generator
import httpx

from app.core.generation.base import AbstractGenerator
from app.config import settings

logger = logging.getLogger(__name__)


class OllamaGenerator(AbstractGenerator):
    """Ollama LLM generator implementation"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: str = "http://localhost:11434"
    ):
        """
        Initialize Ollama generator

        Args:
            model_name: Model name (default: qwen2.5:7b-instruct)
            base_url: Ollama server URL
        """
        model_name = model_name or settings.OLLAMA_MODEL or "qwen2.5:7b-instruct"
        super().__init__(model_name)

        self.provider = "ollama"
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)

        logger.info(f"Initialized Ollama generator with model: {self.model_name}")

    def generate_answer(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Generate answer from context chunks

        Args:
            question: User's question
            context_chunks: List of relevant chunks with metadata
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            include_sources: Whether to include source references

        Returns:
            Generated answer with metadata
        """
        # Build context from chunks
        context = self.build_context(context_chunks)

        # Create prompt
        prompt = self.create_prompt(question, context, include_sources)

        # Generate response
        try:
            response = asyncio.run(
                self._generate_completion_async(prompt, max_tokens, temperature)
            )
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise

        # Process and format response
        return self.format_response(response, context_chunks, include_sources)

    async def _generate_completion_async(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """
        Async Ollama generation

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Response dictionary
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            },
            "stream": False
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            result = response.json()

            return {
                "text": result.get("response", ""),
                "model": self.model_name,
                "tokens_used": {
                    "prompt": result.get("prompt_eval_count", 0),
                    "completion": result.get("eval_count", 0),
                    "total": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                },
                "finish_reason": "completed"
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise

    def generate_streaming(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> Generator[str, None, None]:
        """
        Generate streaming response

        Args:
            question: User's question
            context_chunks: List of relevant chunks
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Yields:
            Response text chunks
        """
        # Build context and prompt
        context = self.build_context(context_chunks)
        prompt = self.create_prompt(question, context, True)

        # Run async streaming in sync context
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def stream_generator():
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature
                    },
                    "stream": True
                }

                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/api/generate",
                        json=payload,
                        timeout=120.0
                    ) as response:
                        async for line in response.aiter_lines():
                            if line:
                                import json
                                try:
                                    data = json.loads(line)
                                    if "response" in data:
                                        yield data["response"]
                                except json.JSONDecodeError:
                                    continue

            # Convert async generator to sync
            async_gen = stream_generator()
            while True:
                try:
                    chunk = loop.run_until_complete(async_gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break

        except Exception as e:
            logger.error(f"Streaming generation error: {e}")
            yield f"Hata oluştu: {str(e)}"
        finally:
            loop.close()

    def summarize_document(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Generate a summary of document chunks

        Args:
            chunks: Document chunks to summarize
            max_tokens: Maximum tokens for summary

        Returns:
            Summary with metadata
        """
        # Combine all chunks
        full_text = "\n\n".join([chunk.get("text", "") for chunk in chunks])

        # Truncate if too long
        if len(full_text) > 10000:
            full_text = full_text[:10000] + "..."

        prompt = f"""Aşağıdaki dokümanın özetini çıkar. Önemli noktaları vurgula ve ana konuları listele.

Dokümant:
{full_text}

Özet:"""

        try:
            response = asyncio.run(
                self._generate_completion_async(prompt, max_tokens, 0.3)
            )
        except Exception as e:
            logger.error(f"Ollama summarization error: {e}")
            raise

        return {
            "summary": response["text"],
            "metadata": {
                "model": self.model_name,
                "provider": self.provider,
                "chunks_processed": len(chunks),
                "tokens_used": response["tokens_used"]
            }
        }

    def check_connection(self) -> bool:
        """
        Check if Ollama server is reachable

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama server not reachable: {e}")
            return False

    def list_models(self) -> List[str]:
        """
        List available models on Ollama server

        Returns:
            List of model names
        """
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    def __del__(self):
        """Cleanup async client"""
        try:
            asyncio.run(self.client.aclose())
        except:
            pass