"""
Base classes for LLM generation
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime


class AbstractGenerator(ABC):
    """Abstract base class for all LLM generator implementations"""

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the generator

        Args:
            model_name: Name of the model to use
        """
        self.model_name = model_name
        self.provider = None

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Build context string from chunks

        Args:
            chunks: List of text chunks

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            doc_id = chunk.get("document_id", "unknown")
            page_num = chunk.get("page_number", chunk.get("metadata", {}).get("page_number", "unknown"))

            context_part = f"[{i}] (Document: {doc_id}, Page: {page_num})\n{text}\n"
            context_parts.append(context_part)

        return "\n".join(context_parts)

    def create_prompt(
        self,
        question: str,
        context: str,
        include_sources: bool = True
    ) -> str:
        """
        Create the prompt for the LLM

        Args:
            question: User's question
            context: Context string
            include_sources: Whether to request source references

        Returns:
            Formatted prompt
        """
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

    def extract_sources(
        self,
        answer: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract source references from the answer

        Args:
            answer: Generated answer text
            chunks: Context chunks used

        Returns:
            List of source references
        """
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
                        "text": chunk.get("text", "")[:200] + "...",
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

    def format_response(
        self,
        response: Dict[str, Any],
        chunks: List[Dict[str, Any]],
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Format the final response with metadata

        Args:
            response: Raw response from LLM
            chunks: Context chunks used
            include_sources: Whether to include sources

        Returns:
            Formatted response dictionary
        """
        answer_text = response.get("text", "")

        # Extract source references from answer
        sources = self.extract_sources(answer_text, chunks) if include_sources else []

        return {
            "answer": answer_text,
            "sources": sources,
            "metadata": {
                "model": response.get("model", self.model_name),
                "provider": self.provider,
                "tokens_used": response.get("tokens_used", {}),
                "context_chunks": len(chunks),
                "generated_at": datetime.now().isoformat(),
                "finish_reason": response.get("finish_reason")
            }
        }