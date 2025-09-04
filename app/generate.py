import logging
import json
from typing import List, Dict, Any, Optional, Generator
import httpx
import openai
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class LLMGenerator:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.setup_client()
    
    def setup_client(self):
        """Setup the LLM client based on provider"""
        if self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not provided")
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4"
        elif self.provider == "ollama":
            self.ollama_url = "http://localhost:11434"
            self.model = settings.OLLAMA_MODEL
            self.client = httpx.AsyncClient()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        
        logger.info(f"Initialized {self.provider} LLM client with model: {self.model}")
    
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
        context = self._build_context(context_chunks)
        
        # Create prompt
        prompt = self._create_prompt(question, context, include_sources)
        
        # Generate response based on provider
        if self.provider == "openai":
            response = self._generate_openai(prompt, max_tokens, temperature)
        elif self.provider == "ollama":
            response = self._generate_ollama(prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        # Process and format response
        return self._format_response(response, context_chunks, include_sources)
    
    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string from chunks"""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            # Format each chunk with source info
            text = chunk.get("text", "")
            doc_id = chunk.get("document_id", "unknown")
            page_num = chunk.get("page_number", chunk.get("metadata", {}).get("page_number", "unknown"))
            
            context_part = f"[{i}] (Document: {doc_id}, Page: {page_num})\n{text}\n"
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _create_prompt(
        self,
        question: str,
        context: str,
        include_sources: bool
    ) -> str:
        """Create the prompt for the LLM"""
        if include_sources:
            system_prompt = """Sen bir uzman hukuk asistansın. Kullanıcının sorularını verilen dokümanlara dayanarak cevaplayacaksın.

Kurallar:
1. Sadece verilen dokümanlardaki bilgileri kullan
2. Her iddian için kaynak belirt (örnek: [1], [2])
3. Eğer sorunun cevabı dokümanlarda yoksa "Bu sorunun cevabı verilen dokümanlarda bulunmuyor" de
4. Türkçe ve net bir şekilde cevap ver
5. Kaynakları cevabın sonunda listele

Dokümantasyon:
{context}

Soru: {question}

Cevap:"""
        else:
            system_prompt = """Sen bir uzman asistansın. Kullanıcının sorularını verilen dokümanlara dayanarak cevaplayacaksın.

Kurallar:
1. Sadece verilen dokümanlardaki bilgileri kullan
2. Eğer sorunun cevabı dokümanlarda yoksa "Bu sorunun cevabı verilen dokümanlarda bulunmuyor" de
3. Türkçe ve net bir şekilde cevap ver

Dokümantasyon:
{context}

Soru: {question}

Cevap:"""
        
        return system_prompt.format(context=context, question=question)
    
    def _generate_openai(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Generate response using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
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
                "model": self.model,
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
    
    def _generate_ollama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Generate response using Ollama"""
        try:
            import asyncio
            return asyncio.run(self._generate_ollama_async(prompt, max_tokens, temperature))
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise
    
    async def _generate_ollama_async(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Async Ollama generation"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()
            
            return {
                "text": result.get("response", ""),
                "model": self.model,
                "tokens_used": {
                    "prompt": result.get("prompt_eval_count", 0),
                    "completion": result.get("eval_count", 0),
                    "total": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                },
                "finish_reason": "completed"
            }
    
    def _format_response(
        self,
        response: Dict[str, Any],
        chunks: List[Dict[str, Any]],
        include_sources: bool
    ) -> Dict[str, Any]:
        """Format the final response with metadata"""
        answer_text = response["text"]
        
        # Extract source references from answer
        sources = self._extract_sources(answer_text, chunks) if include_sources else []
        
        return {
            "answer": answer_text,
            "sources": sources,
            "metadata": {
                "model": response["model"],
                "provider": self.provider,
                "tokens_used": response["tokens_used"],
                "context_chunks": len(chunks),
                "generated_at": datetime.now().isoformat(),
                "finish_reason": response.get("finish_reason")
            }
        }
    
    def _extract_sources(
        self,
        answer: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract source references from the answer"""
        import re
        sources = []
        
        # Find all [number] references in the answer
        references = re.findall(r'\[(\d+)\]', answer)
        
        for ref in references:
            try:
                idx = int(ref) - 1  # Convert to 0-based index
                if 0 <= idx < len(chunks):
                    chunk = chunks[idx]
                    sources.append({
                        "reference": f"[{ref}]",
                        "document_id": chunk.get("document_id", "unknown"),
                        "chunk_id": chunk.get("chunk_id", "unknown"),
                        "page_number": chunk.get("page_number", chunk.get("metadata", {}).get("page_number")),
                        "text": chunk.get("text", "")[:200] + "...",  # Truncate for brevity
                        "score": chunk.get("score", 0.0)
                    })
            except ValueError:
                continue
        
        # Remove duplicates
        seen = set()
        unique_sources = []
        for source in sources:
            key = (source["document_id"], source["chunk_id"])
            if key not in seen:
                seen.add(key)
                unique_sources.append(source)
        
        return unique_sources
    
    def generate_streaming(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> Generator[str, None, None]:
        """Generate streaming response"""
        if self.provider != "openai":
            # Fallback to non-streaming for non-OpenAI providers
            response = self.generate_answer(question, context_chunks, max_tokens, temperature)
            yield response["answer"]
            return
        
        # Build context and prompt
        context = self._build_context(context_chunks)
        prompt = self._create_prompt(question, context, True)
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
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
        """Generate a summary of document chunks"""
        # Combine all chunks
        full_text = "\n\n".join([chunk.get("text", "") for chunk in chunks])
        
        # Truncate if too long (rough token estimation)
        if len(full_text) > 10000:  # ~2500 tokens
            full_text = full_text[:10000] + "..."
        
        prompt = f"""Aşağıdaki dokümanın özetini çıkar. Önemli noktaları vurgula ve ana konuları listele.

Dokümant:
{full_text}

Özet:"""
        
        if self.provider == "openai":
            response = self._generate_openai(prompt, max_tokens, 0.3)
        elif self.provider == "ollama":
            response = self._generate_ollama(prompt, max_tokens, 0.3)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        return {
            "summary": response["text"],
            "metadata": {
                "model": response["model"],
                "provider": self.provider,
                "chunks_processed": len(chunks),
                "generated_at": datetime.now().isoformat()
            }
        }


# Singleton instance
llm_generator = LLMGenerator()