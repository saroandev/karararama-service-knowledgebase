"""
Conversation Manager for chat history persistence
"""
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import text
from app.core.database import db_manager

logger = logging.getLogger(__name__)


class ConversationMessage:
    """Represents a single message in a conversation"""
    def __init__(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        role: str,
        content: str,
        sources: List[Dict[str, Any]] = None,
        tokens_used: int = 0,
        processing_time: float = 0.0,
        created_at: datetime = None,
        message_id: str = None
    ):
        self.message_id = message_id or str(uuid.uuid4())
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.sources = sources or []
        self.tokens_used = tokens_used
        self.processing_time = processing_time
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format"""
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources,
            "tokens_used": self.tokens_used,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ConversationManager:
    """
    Manages conversation history storage and retrieval

    Provides CRUD operations for conversation logs with multi-tenant support.
    """

    def __init__(self):
        self.db = db_manager

    def save_message(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        role: str,
        content: str,
        sources: List[Dict[str, Any]] = None,
        tokens_used: int = 0,
        processing_time: float = 0.0
    ) -> str:
        """
        Save a message to conversation log

        Args:
            conversation_id: Unique conversation identifier
            user_id: User ID
            organization_id: Organization ID
            role: Message role ('user', 'assistant', or 'system')
            content: Message content
            sources: List of source documents used (for assistant messages)
            tokens_used: Tokens consumed for this message
            processing_time: Processing time in seconds

        Returns:
            Message ID (UUID)
        """
        message_id = str(uuid.uuid4())

        import json

        query = """
            INSERT INTO conversation_log (
                id, conversation_id, user_id, organization_id,
                role, content, sources, tokens_used, processing_time
            )
            VALUES (
                :id, :conversation_id, :user_id, :organization_id,
                :role, :content, CAST(:sources AS jsonb), :tokens_used, :processing_time
            )
        """

        params = {
            "id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "role": role,
            "content": content,
            "sources": json.dumps(sources or []),  # Convert to proper JSON string
            "tokens_used": tokens_used,
            "processing_time": processing_time
        }

        try:
            with self.db.get_session() as session:
                session.execute(text(query), params)
            logger.info(f"💾 Saved message {message_id} to conversation {conversation_id}")
            return message_id
        except Exception as e:
            logger.error(f"❌ Failed to save message: {str(e)}")
            raise

    def get_conversation_history(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        limit: int = 10
    ) -> List[ConversationMessage]:
        """
        Retrieve conversation history

        Args:
            conversation_id: Conversation ID
            user_id: User ID (for access control)
            organization_id: Organization ID (for access control)
            limit: Maximum number of messages to retrieve

        Returns:
            List of ConversationMessage objects, ordered by creation time (oldest first)
        """
        query = """
            SELECT
                id, conversation_id, user_id, organization_id,
                role, content, sources, tokens_used, processing_time, created_at
            FROM conversation_log
            WHERE conversation_id = :conversation_id
              AND user_id = :user_id
              AND organization_id = :organization_id
            ORDER BY created_at ASC
            LIMIT :limit
        """

        params = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "limit": limit
        }

        try:
            with self.db.get_session() as session:
                result = session.execute(text(query), params)
                rows = result.fetchall()

            messages = []
            for row in rows:
                msg = ConversationMessage(
                    message_id=str(row[0]),
                    conversation_id=str(row[1]),
                    user_id=row[2],
                    organization_id=row[3],
                    role=row[4],
                    content=row[5],
                    sources=row[6] if row[6] else [],
                    tokens_used=row[7] or 0,
                    processing_time=row[8] or 0.0,
                    created_at=row[9]
                )
                messages.append(msg)

            logger.info(f"📜 Retrieved {len(messages)} messages from conversation {conversation_id}")
            return messages

        except Exception as e:
            logger.error(f"❌ Failed to retrieve conversation history: {str(e)}")
            return []

    def get_context_for_llm(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get formatted conversation context for LLM

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            organization_id: Organization ID
            max_messages: Maximum number of messages to include

        Returns:
            List of messages in OpenAI chat format: [{"role": "user", "content": "..."}]
        """
        messages = self.get_conversation_history(
            conversation_id, user_id, organization_id, limit=max_messages
        )

        # Convert to OpenAI chat format
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return formatted_messages

    def create_new_conversation(self) -> str:
        """
        Create a new conversation ID

        Returns:
            New conversation ID (UUID)
        """
        conversation_id = str(uuid.uuid4())
        logger.info(f"🆕 Created new conversation: {conversation_id}")
        return conversation_id

    def delete_conversation(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str
    ) -> int:
        """
        Delete all messages in a conversation

        Args:
            conversation_id: Conversation ID to delete
            user_id: User ID (for access control)
            organization_id: Organization ID (for access control)

        Returns:
            Number of messages deleted
        """
        query = """
            DELETE FROM conversation_log
            WHERE conversation_id = :conversation_id
              AND user_id = :user_id
              AND organization_id = :organization_id
        """

        params = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "organization_id": organization_id
        }

        try:
            with self.db.get_session() as session:
                result = session.execute(text(query), params)
                deleted_count = result.rowcount

            logger.info(f"🗑️ Deleted {deleted_count} messages from conversation {conversation_id}")
            return deleted_count

        except Exception as e:
            logger.error(f"❌ Failed to delete conversation: {str(e)}")
            raise

    def get_user_conversations(
        self,
        user_id: str,
        organization_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get list of user's conversations with summary

        Args:
            user_id: User ID
            organization_id: Organization ID
            limit: Maximum number of conversations to return

        Returns:
            List of conversation summaries
        """
        query = """
            SELECT
                conversation_id,
                COUNT(*) as message_count,
                MIN(created_at) as started_at,
                MAX(created_at) as last_message_at
            FROM conversation_log
            WHERE user_id = :user_id
              AND organization_id = :organization_id
            GROUP BY conversation_id
            ORDER BY MAX(created_at) DESC
            LIMIT :limit
        """

        params = {
            "user_id": user_id,
            "organization_id": organization_id,
            "limit": limit
        }

        try:
            with self.db.get_session() as session:
                result = session.execute(text(query), params)
                rows = result.fetchall()

            conversations = []
            for row in rows:
                conversations.append({
                    "conversation_id": str(row[0]),
                    "message_count": row[1],
                    "started_at": row[2].isoformat() if row[2] else None,
                    "last_message_at": row[3].isoformat() if row[3] else None
                })

            logger.info(f"📋 Retrieved {len(conversations)} conversations for user {user_id}")
            return conversations

        except Exception as e:
            logger.error(f"❌ Failed to retrieve user conversations: {str(e)}")
            return []


# Global conversation manager instance
conversation_manager = ConversationManager()
