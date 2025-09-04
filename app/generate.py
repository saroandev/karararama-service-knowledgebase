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
            
            context_part = f"[{i}] (Document: {doc_id}, Page: {page_num})\\n{text}\\n"\n            context_parts.append(context_part)
        
        return "\\n".join(context_parts)
    
    def _create_prompt(
        self,\n        question: str,\n        context: str,\n        include_sources: bool\n    ) -> str:\n        \"\"\"Create the prompt for the LLM\"\"\"\n        if include_sources:\n            system_prompt = \"\"\"Sen bir uzman asistans1n. Kullan1c1n1n sorular1n1 verilen dokümanlara dayanarak cevaplayacaks1n.\n\nKurallar:\n1. Sadece verilen dokümanlardaki bilgileri kullan\n2. Her iddiay1n için kaynak belirt (örnek: [1], [2])\n3. Eer sorunun cevab1 dokümanlarda yoksa \"Bu sorunun cevab1 verilen dokümanlarda bulunmuyor\" de\n4. Türkçe ve net bir _ekilde cevap ver\n5. Kaynaklar1 cevab1n sonunda listele\n\nDokümantasyon:\n{context}\n\nSoru: {question}\n\nCevap:\"\"\"\n        else:\n            system_prompt = \"\"\"Sen bir uzman asistans1n. Kullan1c1n1n sorular1n1 verilen dokümanlara dayanarak cevaplayacaks1n.\n\nKurallar:\n1. Sadece verilen dokümanlardaki bilgileri kullan\n2. Eer sorunun cevab1 dokümanlarda yoksa \"Bu sorunun cevab1 verilen dokümanlarda bulunmuyor\" de\n3. Türkçe ve net bir _ekilde cevap ver\n\nDokümantasyon:\n{context}\n\nSoru: {question}\n\nCevap:\"\"\"\n        \n        return system_prompt.format(context=context, question=question)\n    \n    def _generate_openai(\n        self,\n        prompt: str,\n        max_tokens: int,\n        temperature: float\n    ) -> Dict[str, Any]:\n        \"\"\"Generate response using OpenAI\"\"\"\n        try:\n            response = self.client.chat.completions.create(\n                model=self.model,\n                messages=[\n                    {\"role\": \"system\", \"content\": \"Sen yard1mc1 bir asistans1n.\"},\n                    {\"role\": \"user\", \"content\": prompt}\n                ],\n                max_tokens=max_tokens,\n                temperature=temperature,\n                stream=False\n            )\n            \n            return {\n                \"text\": response.choices[0].message.content,\n                \"model\": self.model,\n                \"tokens_used\": {\n                    \"prompt\": response.usage.prompt_tokens,\n                    \"completion\": response.usage.completion_tokens,\n                    \"total\": response.usage.total_tokens\n                },\n                \"finish_reason\": response.choices[0].finish_reason\n            }\n            \n        except Exception as e:\n            logger.error(f\"OpenAI generation error: {e}\")\n            raise\n    \n    def _generate_ollama(\n        self,\n        prompt: str,\n        max_tokens: int,\n        temperature: float\n    ) -> Dict[str, Any]:\n        \"\"\"Generate response using Ollama\"\"\"\n        try:\n            import asyncio\n            return asyncio.run(self._generate_ollama_async(prompt, max_tokens, temperature))\n        except Exception as e:\n            logger.error(f\"Ollama generation error: {e}\")\n            raise\n    \n    async def _generate_ollama_async(\n        self,\n        prompt: str,\n        max_tokens: int,\n        temperature: float\n    ) -> Dict[str, Any]:\n        \"\"\"Async Ollama generation\"\"\"\n        payload = {\n            \"model\": self.model,\n            \"prompt\": prompt,\n            \"max_tokens\": max_tokens,\n            \"temperature\": temperature,\n            \"stream\": False\n        }\n        \n        async with httpx.AsyncClient() as client:\n            response = await client.post(\n                f\"{self.ollama_url}/api/generate\",\n                json=payload,\n                timeout=60.0\n            )\n            response.raise_for_status()\n            result = response.json()\n            \n            return {\n                \"text\": result.get(\"response\", \"\"),\n                \"model\": self.model,\n                \"tokens_used\": {\n                    \"prompt\": result.get(\"prompt_eval_count\", 0),\n                    \"completion\": result.get(\"eval_count\", 0),\n                    \"total\": result.get(\"prompt_eval_count\", 0) + result.get(\"eval_count\", 0)\n                },\n                \"finish_reason\": \"completed\"\n            }\n    \n    def _format_response(\n        self,\n        response: Dict[str, Any],\n        chunks: List[Dict[str, Any]],\n        include_sources: bool\n    ) -> Dict[str, Any]:\n        \"\"\"Format the final response with metadata\"\"\"\n        answer_text = response[\"text\"]\n        \n        # Extract source references from answer\n        sources = self._extract_sources(answer_text, chunks) if include_sources else []\n        \n        return {\n            \"answer\": answer_text,\n            \"sources\": sources,\n            \"metadata\": {\n                \"model\": response[\"model\"],\n                \"provider\": self.provider,\n                \"tokens_used\": response[\"tokens_used\"],\n                \"context_chunks\": len(chunks),\n                \"generated_at\": datetime.now().isoformat(),\n                \"finish_reason\": response.get(\"finish_reason\")\n            }\n        }\n    \n    def _extract_sources(\n        self,\n        answer: str,\n        chunks: List[Dict[str, Any]]\n    ) -> List[Dict[str, Any]]:\n        \"\"\"Extract source references from the answer\"\"\"\n        import re\n        sources = []\n        \n        # Find all [number] references in the answer\n        references = re.findall(r'\\[(\\d+)\\]', answer)\n        \n        for ref in references:\n            try:\n                idx = int(ref) - 1  # Convert to 0-based index\n                if 0 <= idx < len(chunks):\n                    chunk = chunks[idx]\n                    sources.append({\n                        \"reference\": f\"[{ref}]\",\n                        \"document_id\": chunk.get(\"document_id\", \"unknown\"),\n                        \"chunk_id\": chunk.get(\"chunk_id\", \"unknown\"),\n                        \"page_number\": chunk.get(\"page_number\", chunk.get(\"metadata\", {}).get(\"page_number\")),\n                        \"text\": chunk.get(\"text\", \"\")[:200] + \"...\",  # Truncate for brevity\n                        \"score\": chunk.get(\"score\", 0.0)\n                    })\n            except ValueError:\n                continue\n        \n        # Remove duplicates\n        seen = set()\n        unique_sources = []\n        for source in sources:\n            key = (source[\"document_id\"], source[\"chunk_id\"])\n            if key not in seen:\n                seen.add(key)\n                unique_sources.append(source)\n        \n        return unique_sources\n    \n    def generate_streaming(\n        self,\n        question: str,\n        context_chunks: List[Dict[str, Any]],\n        max_tokens: int = 1000,\n        temperature: float = 0.1\n    ) -> Generator[str, None, None]:\n        \"\"\"Generate streaming response\"\"\"\n        if self.provider != \"openai\":\n            # Fallback to non-streaming for non-OpenAI providers\n            response = self.generate_answer(question, context_chunks, max_tokens, temperature)\n            yield response[\"answer\"]\n            return\n        \n        # Build context and prompt\n        context = self._build_context(context_chunks)\n        prompt = self._create_prompt(question, context, True)\n        \n        try:\n            stream = self.client.chat.completions.create(\n                model=self.model,\n                messages=[\n                    {\"role\": \"system\", \"content\": \"Sen yard1mc1 bir asistans1n.\"},\n                    {\"role\": \"user\", \"content\": prompt}\n                ],\n                max_tokens=max_tokens,\n                temperature=temperature,\n                stream=True\n            )\n            \n            for chunk in stream:\n                if chunk.choices[0].delta.content is not None:\n                    yield chunk.choices[0].delta.content\n                    \n        except Exception as e:\n            logger.error(f\"Streaming generation error: {e}\")\n            yield f\"Hata olu_tu: {str(e)}\"\n    \n    def summarize_document(\n        self,\n        chunks: List[Dict[str, Any]],\n        max_tokens: int = 500\n    ) -> Dict[str, Any]:\n        \"\"\"Generate a summary of document chunks\"\"\"\n        # Combine all chunks\n        full_text = \"\\n\\n\".join([chunk.get(\"text\", \"\") for chunk in chunks])\n        \n        # Truncate if too long (rough token estimation)\n        if len(full_text) > 10000:  # ~2500 tokens\n            full_text = full_text[:10000] + \"...\"\n        \n        prompt = f\"\"\"A_a1daki doküman1n özetini ç1kar. Önemli noktalar1 vurgula ve ana konular1 listele.\n\nDokümant:\n{full_text}\n\nÖzet:\"\"\"\n        \n        if self.provider == \"openai\":\n            response = self._generate_openai(prompt, max_tokens, 0.3)\n        elif self.provider == \"ollama\":\n            response = self._generate_ollama(prompt, max_tokens, 0.3)\n        else:\n            raise ValueError(f\"Unsupported provider: {self.provider}\")\n        \n        return {\n            \"summary\": response[\"text\"],\n            \"metadata\": {\n                \"model\": response[\"model\"],\n                \"provider\": self.provider,\n                \"chunks_processed\": len(chunks),\n                \"generated_at\": datetime.now().isoformat()\n            }\n        }\n\n\n# Singleton instance\nllm_generator = LLMGenerator()