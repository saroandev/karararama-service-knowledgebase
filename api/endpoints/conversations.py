"""
Conversation history endpoints
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.conversation import conversation_manager
from app.core.auth import UserContext, get_current_user
from schemas.api.responses.conversation import (
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationDeleteResponse,
    ConversationSummaryResponse,
    ConversationMessageResponse
)

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
