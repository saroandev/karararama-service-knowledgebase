"""
Conversation history endpoints

These endpoints are used by:
1. Frontend/UI for displaying conversation history
2. Orchestrator service for saving messages and getting LLM context
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.core.conversation import conversation_manager
from app.core.auth import UserContext, get_current_user
from schemas.api.responses.conversation import (
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationDeleteResponse,
    ConversationSummaryResponse,
    ConversationMessageResponse
)


# Request/Response models for orchestrator endpoints
class SaveMessageRequest(BaseModel):
    """Request to save a message to conversation"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    sources: Optional[List[Dict[str, Any]]] = Field(default=None, description="Sources used (for assistant messages)")
    tokens_used: int = Field(default=0, description="Tokens consumed")
    processing_time: float = Field(default=0.0, description="Processing time in seconds")


class SaveMessageResponse(BaseModel):
    """Response after saving a message"""
    message_id: str = Field(..., description="Created message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    success: bool = Field(default=True)


class LLMContextResponse(BaseModel):
    """LLM-formatted conversation context"""
    conversation_id: str = Field(..., description="Conversation ID")
    messages: List[Dict[str, str]] = Field(..., description="Messages in OpenAI chat format")
    message_count: int = Field(..., description="Number of messages returned")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=ConversationListResponse, summary="List all user conversations")
async def list_conversations(
    limit: int = 20,
    user: UserContext = Depends(get_current_user)
):
    """
    Retrieve a list of all conversations for the current user.

    Returns conversations ordered by most recent activity first.

    **Parameters:**
    - **limit**: Maximum number of conversations to return (default: 20, max: 100)

    **Returns:**
    - List of conversation summaries with message count and timestamps
    - Total count of user's conversations

    **Authentication:**
    - Requires valid JWT token
    - Only returns conversations belonging to the authenticated user
    """
    if limit > 100:
        limit = 100

    try:
        # Get conversation summaries
        conversations_data = conversation_manager.get_user_conversations(
            user_id=user.user_id,
            organization_id=user.organization_id,
            limit=limit
        )

        # For each conversation, get the first message for preview
        conversation_summaries = []
        for conv_data in conversations_data:
            # Get first message for preview
            messages = conversation_manager.get_conversation_history(
                conversation_id=conv_data["conversation_id"],
                user_id=user.user_id,
                organization_id=user.organization_id,
                limit=1
            )

            first_message_preview = ""
            if messages:
                first_message_preview = messages[0].content[:100]

            conversation_summaries.append(
                ConversationSummaryResponse(
                    conversation_id=conv_data["conversation_id"],
                    message_count=conv_data["message_count"],
                    first_message_preview=first_message_preview,
                    started_at=conv_data["started_at"],
                    last_message_at=conv_data["last_message_at"]
                )
            )

        logger.info(f"📋 User {user.user_id} retrieved {len(conversation_summaries)} conversations")

        return ConversationListResponse(
            conversations=conversation_summaries,
            total_count=len(conversation_summaries)
        )

    except Exception as e:
        logger.error(f"❌ Failed to list conversations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversations"
        )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse, summary="Get conversation details")
async def get_conversation(
    conversation_id: str,
    limit: int = 100,
    user: UserContext = Depends(get_current_user)
):
    """
    Retrieve detailed conversation history with all messages.

    Returns all messages in chronological order (oldest first).

    **Parameters:**
    - **conversation_id**: Unique conversation identifier
    - **limit**: Maximum number of messages to return (default: 100)

    **Returns:**
    - Complete conversation details including all messages
    - Metadata: user_id, organization_id, message count, timestamps

    **Authentication:**
    - Requires valid JWT token
    - Only allows access to user's own conversations

    **Errors:**
    - 404: Conversation not found or user doesn't have access
    """
    try:
        # Get conversation messages
        messages = conversation_manager.get_conversation_history(
            conversation_id=conversation_id,
            user_id=user.user_id,
            organization_id=user.organization_id,
            limit=limit
        )

        if not messages:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found or you don't have access"
            )

        # Convert to response format
        message_responses = []
        for msg in messages:
            message_responses.append(
                ConversationMessageResponse(
                    message_id=msg.message_id,
                    role=msg.role,
                    content=msg.content,
                    sources=msg.sources,
                    tokens_used=msg.tokens_used,
                    processing_time=msg.processing_time,
                    created_at=msg.created_at.isoformat() if msg.created_at else ""
                )
            )

        # Get conversation metadata
        first_message = messages[0]
        last_message = messages[-1]

        logger.info(f"💬 User {user.user_id} retrieved conversation {conversation_id} with {len(messages)} messages")

        return ConversationDetailResponse(
            conversation_id=conversation_id,
            user_id=user.user_id,
            organization_id=user.organization_id,
            message_count=len(messages),
            messages=message_responses,
            started_at=first_message.created_at.isoformat() if first_message.created_at else "",
            last_message_at=last_message.created_at.isoformat() if last_message.created_at else ""
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation"
        )


@router.delete("/{conversation_id}", response_model=ConversationDeleteResponse, summary="Delete conversation")
async def delete_conversation(
    conversation_id: str,
    user: UserContext = Depends(get_current_user)
):
    """
    Delete a conversation and all its messages permanently.

    This operation cannot be undone.

    **Parameters:**
    - **conversation_id**: Unique conversation identifier to delete

    **Returns:**
    - Success message
    - Deleted conversation ID
    - Number of messages deleted

    **Authentication:**
    - Requires valid JWT token
    - Only allows deletion of user's own conversations

    **Errors:**
    - 404: Conversation not found or user doesn't have access
    """
    try:
        # Attempt to delete conversation
        deleted_count = conversation_manager.delete_conversation(
            conversation_id=conversation_id,
            user_id=user.user_id,
            organization_id=user.organization_id
        )

        if deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found or you don't have access"
            )

        logger.info(f"🗑️ User {user.user_id} deleted conversation {conversation_id} ({deleted_count} messages)")

        return ConversationDeleteResponse(
            message="Conversation deleted successfully",
            conversation_id=conversation_id,
            messages_deleted=deleted_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )


# ============================================================================
# ORCHESTRATOR ENDPOINTS
# These endpoints are designed for the orchestrator service to use
# ============================================================================

@router.post("/{conversation_id}/messages", response_model=SaveMessageResponse, summary="Save message to conversation")
async def save_message(
    conversation_id: str,
    request: SaveMessageRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Save a message to conversation history.

    This endpoint is primarily used by the orchestrator service to save
    user questions and assistant answers to the conversation log.

    **Parameters:**
    - **conversation_id**: Unique conversation identifier
    - **role**: Message role ('user' or 'assistant')
    - **content**: Message content
    - **sources**: Optional list of sources (for assistant messages)
    - **tokens_used**: Tokens consumed for this message
    - **processing_time**: Processing time in seconds

    **Returns:**
    - message_id: Created message UUID
    - conversation_id: Echo of the conversation ID
    - success: Boolean indicating success

    **Authentication:**
    - Requires valid JWT token
    - Message is scoped to the authenticated user and organization
    """
    try:
        # Validate role
        if request.role not in ["user", "assistant", "system"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {request.role}. Must be 'user', 'assistant', or 'system'"
            )

        # Save message
        message_id = conversation_manager.save_message(
            conversation_id=conversation_id,
            user_id=user.user_id,
            organization_id=user.organization_id,
            role=request.role,
            content=request.content,
            sources=request.sources,
            tokens_used=request.tokens_used,
            processing_time=request.processing_time
        )

        logger.info(f"💾 Saved {request.role} message to conversation {conversation_id}")

        return SaveMessageResponse(
            message_id=message_id,
            conversation_id=conversation_id,
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to save message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save message: {str(e)}"
        )


@router.get("/{conversation_id}/context", response_model=LLMContextResponse, summary="Get LLM context")
async def get_llm_context(
    conversation_id: str,
    max_messages: int = 10,
    user: UserContext = Depends(get_current_user)
):
    """
    Get conversation context formatted for LLM.

    Returns messages in OpenAI chat completion format, ready to be used
    as conversation history in LLM calls.

    **Parameters:**
    - **conversation_id**: Unique conversation identifier
    - **max_messages**: Maximum number of messages to return (default: 10)

    **Returns:**
    - conversation_id: Echo of the conversation ID
    - messages: List of messages in format [{"role": "user", "content": "..."}]
    - message_count: Number of messages returned

    **Authentication:**
    - Requires valid JWT token
    - Only returns messages from authenticated user's conversations

    **Example Response:**
    ```json
    {
        "conversation_id": "conv-123",
        "messages": [
            {"role": "user", "content": "What is RAG?"},
            {"role": "assistant", "content": "RAG stands for..."}
        ],
        "message_count": 2
    }
    ```
    """
    try:
        # Get formatted context
        messages = conversation_manager.get_context_for_llm(
            conversation_id=conversation_id,
            user_id=user.user_id,
            organization_id=user.organization_id,
            max_messages=max_messages
        )

        logger.info(f"📜 Retrieved {len(messages)} messages for LLM context from {conversation_id}")

        return LLMContextResponse(
            conversation_id=conversation_id,
            messages=messages,
            message_count=len(messages)
        )

    except Exception as e:
        logger.error(f"❌ Failed to get LLM context: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation context: {str(e)}"
        )
