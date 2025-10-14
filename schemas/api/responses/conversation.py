"""
Conversation history response schemas
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ConversationMessageResponse(BaseModel):
    """Single message in a conversation"""
    message_id: str = Field(..., description="Unique message identifier")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    sources: List[Dict[str, Any]] = Field(default=[], description="Sources used (for assistant messages)")
    tokens_used: int = Field(default=0, description="Tokens consumed for this message")
    processing_time: float = Field(default=0.0, description="Processing time in seconds")
    created_at: str = Field(..., description="Message timestamp (ISO format)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message_id": "msg-123",
                "role": "user",
                "content": "İcra ve İflas Kanunu nedir?",
                "sources": [],
                "tokens_used": 0,
                "processing_time": 0.0,
                "created_at": "2025-10-14T19:00:00Z"
            }
        }
    }


class ConversationDetailResponse(BaseModel):
    """Detailed conversation with all messages"""
    conversation_id: str = Field(..., description="Conversation identifier")
    user_id: str = Field(..., description="User who owns this conversation")
    organization_id: str = Field(..., description="Organization ID")
    message_count: int = Field(..., description="Total number of messages")
    messages: List[ConversationMessageResponse] = Field(..., description="All messages in chronological order")
    started_at: str = Field(..., description="First message timestamp (ISO format)")
    last_message_at: str = Field(..., description="Last message timestamp (ISO format)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation_id": "conv-123",
                "user_id": "user-456",
                "organization_id": "org-789",
                "message_count": 4,
                "messages": [
                    {
                        "message_id": "msg-1",
                        "role": "user",
                        "content": "2+4 kaçtır?",
                        "sources": [],
                        "tokens_used": 0,
                        "processing_time": 0.0,
                        "created_at": "2025-10-14T19:00:00Z"
                    },
                    {
                        "message_id": "msg-2",
                        "role": "assistant",
                        "content": "6",
                        "sources": [],
                        "tokens_used": 50,
                        "processing_time": 1.2,
                        "created_at": "2025-10-14T19:00:02Z"
                    }
                ],
                "started_at": "2025-10-14T19:00:00Z",
                "last_message_at": "2025-10-14T19:00:02Z"
            }
        }
    }


class ConversationSummaryResponse(BaseModel):
    """Summary of a conversation (for listing)"""
    conversation_id: str = Field(..., description="Conversation identifier")
    message_count: int = Field(..., description="Total number of messages")
    first_message_preview: str = Field(..., description="Preview of the first user message (max 100 chars)")
    started_at: str = Field(..., description="First message timestamp (ISO format)")
    last_message_at: str = Field(..., description="Last message timestamp (ISO format)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation_id": "conv-123",
                "message_count": 4,
                "first_message_preview": "2+4 kaçtır?",
                "started_at": "2025-10-14T19:00:00Z",
                "last_message_at": "2025-10-14T19:00:10Z"
            }
        }
    }


class ConversationListResponse(BaseModel):
    """List of user's conversations"""
    conversations: List[ConversationSummaryResponse] = Field(..., description="List of conversations")
    total_count: int = Field(..., description="Total number of conversations")

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversations": [
                    {
                        "conversation_id": "conv-123",
                        "message_count": 4,
                        "first_message_preview": "İcra ve İflas Kanunu nedir?",
                        "started_at": "2025-10-14T19:00:00Z",
                        "last_message_at": "2025-10-14T19:00:10Z"
                    }
                ],
                "total_count": 1
            }
        }
    }


class ConversationDeleteResponse(BaseModel):
    """Response after deleting a conversation"""
    message: str = Field(..., description="Success message")
    conversation_id: str = Field(..., description="Deleted conversation ID")
    messages_deleted: int = Field(..., description="Number of messages deleted")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Conversation deleted successfully",
                "conversation_id": "conv-123",
                "messages_deleted": 4
            }
        }
    }
