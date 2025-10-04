"""
Query endpoint for document search
"""
import datetime
import json
import logging
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Depends
from openai import OpenAI

from schemas.api.requests.query import QueryRequest
from schemas.api.responses.query import QueryResponse, QuerySource
from api.core.milvus_manager import milvus_manager
from api.core.dependencies import retry_with_backoff
from api.core.embeddings import embedding_service
from app.config import settings
from app.core.storage import storage
from app.core.auth import UserContext, require_permission
from app.services.auth_service import get_auth_service_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
@retry_with_backoff(max_retries=3)
async def query_documents(
    request: QueryRequest,
    user: UserContext = Depends(require_permission("research", "query"))
) -> QueryResponse:
    """
    Production query endpoint with persistent storage

    Requires:
    - Valid JWT token in Authorization header
    - User must have 'research:query' permission
    """
    start_time = datetime.datetime.now()

    try:
        logger.info(f"Query: {request.question}")

        # Connect to Milvus
        collection = milvus_manager.get_collection()

        # Generate query embedding
        query_embedding = embedding_service.generate_embedding(request.question)

        # No filters - search in all documents
        expr = None

        # Vector search
        search_results = collection.search(
            [query_embedding],
            'embedding',
            {'metric_type': 'COSINE'},  # COSINE metric to match collection index
            limit=request.top_k,
            expr=expr,
            output_fields=['document_id', 'chunk_index', 'text', 'metadata']
        )

        if not search_results[0]:
            return QueryResponse(
                answer="İlgili bilgi bulunamadı.",
                sources=[],
                processing_time=0,
                model_used="gpt-4o-mini"
            )

        # Prepare context
        sources = []
        context_parts = []

        # Cache for document metadata
        doc_metadata_cache = {}

        for i, result in enumerate(search_results[0]):
            score = result.score
            # Access entity fields directly as attributes
            doc_id = result.entity.document_id
            chunk_index = result.entity.chunk_index if hasattr(result.entity, 'chunk_index') else 0
            text = result.entity.text if hasattr(result.entity, 'text') else ''
            metadata = result.entity.metadata if hasattr(result.entity, 'metadata') else {}

            # Parse metadata (now it's a dict, not JSON string)
            if isinstance(metadata, str):
                meta_dict = json.loads(metadata)
            else:
                meta_dict = metadata if metadata else {}

            # Get the original filename from metadata
            document_title = meta_dict.get('document_title', 'Unknown')

            # Try to get better metadata from MinIO if needed
            if doc_id not in doc_metadata_cache:
                doc_metadata_cache[doc_id] = storage.get_document_metadata(doc_id)

            # Use document title from Milvus metadata, fallback to MinIO metadata
            if document_title and document_title != 'Unknown':
                original_filename = f"{document_title}.pdf" if not document_title.endswith('.pdf') else document_title
            elif doc_id in doc_metadata_cache:
                original_filename = doc_metadata_cache[doc_id].get("original_filename", f'{doc_id}.pdf')
            else:
                original_filename = f'{doc_id}.pdf'

            doc_title = document_title if document_title != 'Unknown' else original_filename.replace('.pdf', '')
            chunk_id = meta_dict.get('chunk_id', f'chunk_{chunk_index}')
            page_num = meta_dict.get('page_number', 0)
            created_at = meta_dict.get('created_at', 0)

            # Generate document URL for MinIO console (properly encoded)
            encoded_filename = quote(original_filename)
            document_url = f"http://localhost:9001/browser/raw-documents/{doc_id}/{encoded_filename}"

            sources.append(QuerySource(
                rank=i + 1,
                score=round(score, 3),
                document_id=doc_id,
                document_name=original_filename,
                document_title=doc_title,
                document_url=document_url,
                page_number=page_num,
                text_preview=text[:200] + "..." if len(text) > 200 else text,
                created_at=created_at
            ))

            context_parts.append(f"[Kaynak {i+1} - Sayfa {page_num}]: {text}")

        # Generate answer
        context = "\n\n".join(context_parts)

        # Generate answer using OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        chat_response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """Sen yardımsever bir RAG (Retrieval-Augmented Generation) asistanısın.

GÖREVİN:
• Verilen kaynak belgelerden faydalanarak soruları net ve anlaşılır şekilde cevaplamak
• Cevaplarını Türkçe dilbilgisi kurallarına uygun, akıcı bir dille yazmak
• Her zaman kaynak numaralarını belirtmek (Örn: [Kaynak 1], [Kaynak 2-3])

CEVAP FORMATI:
1. Soruya doğrudan ve özlü bir cevap ver
2. Gerekirse madde madde veya paragraflar halinde açıkla
3. Her bilgi için hangi kaynaktan alındığını belirt
4. Eğer sorunun cevabı kaynak belgelerde yoksa, "Sağlanan kaynaklarda bu soruya ilişkin bilgi bulunmamaktadır" de

ÖNEMLI:
• Sadece verilen kaynaklardaki bilgileri kullan
• Kendi bilgini ekleme, sadece kaynakları yorumla
• Belirsizlik varsa bunu belirt"""
                },
                {
                    "role": "user",
                    "content": f"""Kaynak Belgeler:
{context}

Soru: {request.question}

Lütfen bu soruya kaynak belgelere dayanarak cevap ver ve hangi kaynak(lardan) bilgi aldığını belirt."""
                }
            ],
            max_tokens=500
        )

        answer = chat_response.choices[0].message.content
        model_used = settings.OPENAI_MODEL

        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        # Get token usage from OpenAI response
        tokens_used = chat_response.usage.total_tokens if hasattr(chat_response, 'usage') else 0

        # Report usage to auth service
        auth_client = get_auth_service_client()
        remaining_credits = user.remaining_credits

        try:
            usage_result = await auth_client.consume_usage(
                user_id=user.user_id,
                service_type="rag_query",
                tokens_used=tokens_used,
                processing_time=processing_time,
                metadata={
                    "question_length": len(request.question),
                    "sources_count": len(sources),
                    "model": model_used,
                    "top_k": request.top_k
                }
            )

            # Update credits from auth service response
            if usage_result.get("remaining_credits") is not None:
                remaining_credits = usage_result.get("remaining_credits")

        except Exception as e:
            # Log but don't fail the request (already processed)
            logger.warning(f"Failed to report usage to auth service: {str(e)}")

        logger.info(f"Query completed in {processing_time:.2f}s")

        return QueryResponse(
            answer=answer,
            sources=sources,
            processing_time=processing_time,
            model_used=model_used,
            tokens_used=tokens_used,
            remaining_credits=remaining_credits
        )

    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")