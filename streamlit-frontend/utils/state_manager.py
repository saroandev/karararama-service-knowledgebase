"""
Session state management utilities
"""
import streamlit as st
import uuid
from datetime import datetime
from typing import Optional


class StateManager:
    """Manages Streamlit session state"""

    @staticmethod
    def initialize():
        """Initialize all session state variables"""
        if 'conversations' not in st.session_state:
            st.session_state.conversations = []

        if 'current_conversation_id' not in st.session_state:
            st.session_state.current_conversation_id = None

        if 'messages' not in st.session_state:
            st.session_state.messages = []

        if 'processed_files' not in st.session_state:
            st.session_state.processed_files = set()

        if 'uploaded_documents' not in st.session_state:
            st.session_state.uploaded_documents = []


        if 'processing_query' not in st.session_state:
            st.session_state.processing_query = False

        if 'show_documents_modal' not in st.session_state:
            st.session_state.show_documents_modal = False

        if 'knowledge_base_documents' not in st.session_state:
            st.session_state.knowledge_base_documents = []

    @staticmethod
    def create_new_conversation() -> str:
        """Create a new conversation and return its ID"""
        conversation_id = str(uuid.uuid4())
        conversation = {
            'id': conversation_id,
            'title': f"Konuşma {len(st.session_state.conversations) + 1}",
            'created_at': datetime.now().isoformat(),
            'messages': []
        }
        st.session_state.conversations.append(conversation)
        st.session_state.current_conversation_id = conversation_id
        st.session_state.messages = []
        return conversation_id

    @staticmethod
    def load_conversation(conversation_id: str):
        """Load a specific conversation"""
        for conv in st.session_state.conversations:
            if conv['id'] == conversation_id:
                st.session_state.current_conversation_id = conversation_id
                st.session_state.messages = conv['messages']
                break

    @staticmethod
    def save_current_conversation():
        """Save the current conversation state"""
        if st.session_state.current_conversation_id:
            for conv in st.session_state.conversations:
                if conv['id'] == st.session_state.current_conversation_id:
                    conv['messages'] = st.session_state.messages
                    # Update title based on first message
                    if st.session_state.messages and len(st.session_state.messages) > 0:
                        first_user_msg = next(
                            (msg['content'] for msg in st.session_state.messages if msg['role'] == 'user'),
                            None
                        )
                        if first_user_msg:
                            conv['title'] = first_user_msg[:30] + "..." if len(first_user_msg) > 30 else first_user_msg
                    break

    @staticmethod
    def add_message(role: str, content: str, sources: Optional[list] = None):
        """Add a message to the current conversation"""
        message = {"role": role, "content": content}
        if sources:
            message["sources"] = sources
        st.session_state.messages.append(message)
        StateManager.save_current_conversation()

    @staticmethod
    def add_uploaded_document(filename: str, document_id: str, chunks: int):
        """Add document to uploaded documents list"""
        st.session_state.uploaded_documents.append({
            'filename': filename,
            'document_id': document_id,
            'chunks': chunks,
            'upload_time': datetime.now().isoformat()
        })

