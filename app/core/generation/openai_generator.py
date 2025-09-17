"""
OpenAI LLM generator implementation
"""
import logging
from typing import List, Dict, Any, Optional, Generator
import openai

from app.core.generation.base import AbstractGenerator
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIGenerator(AbstractGenerator):
    """OpenAI LLM generator implementation"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        """
        Initialize OpenAI generator

        Args:
            api_key: OpenAI API key (uses settings if not provided)
            model_name: Model name (default: gpt-4o-mini)
        """
        model_name = model_name or settings.OPENAI_MODEL or "gpt-4o-mini"
        super().__init__(model_name)

        self.provider = "openai"
        self.api_key = api_key or settings.OPENAI_API_KEY

        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)

        logger.info(f"Initialized OpenAI generator with model: {self.model_name}")

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
        response = self._generate_completion(prompt, max_tokens, temperature)

        # Process and format response
        return self.format_response(response, context_chunks, include_sources)

    def _generate_completion(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """
        Generate completion using OpenAI API

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Response dictionary
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Sen yardımcı bir asistansın."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False
            )

            return {
                "text": response.choices[0].message.content,
                "model": self.model_name,
                "tokens_used": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                },
                "finish_reason": response.choices[0].finish_reason
            }

        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
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

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Sen yardımcı bir asistansın."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Streaming generation error: {e}")
            yield f"Hata oluştu: {str(e)}"

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

        # Truncate if too long (rough token estimation)
        if len(full_text) > 10000:  # ~2500 tokens
            full_text = full_text[:10000] + "..."

        prompt = f"""Aşağıdaki dokümanın özetini çıkar. Önemli noktaları vurgula ve ana konuları listele.

Dokümant:
{full_text}

Özet:"""

        response = self._generate_completion(prompt, max_tokens, 0.3)

        return {
            "summary": response["text"],
            "metadata": {
                "model": self.model_name,
                "provider": self.provider,
                "chunks_processed": len(chunks),
                "tokens_used": response["tokens_used"]
            }
        }