"""
Main Streamlit Application Entry Point
"""
import streamlit as st
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

# Import configuration
from config.settings import PAGE_CONFIG

# Import styles
from styles.custom_css import get_custom_css

# Import utilities
from utils.state_manager import StateManager

# Import components
from components.sidebar import render_sidebar
from components.chat import render_chat_messages, handle_chat_input
from components.documents import render_documents_modal
from components.file_upload import render_file_upload
from components.system_status import render_system_status


def main():
    """Main application function"""
    # Page configuration
    st.set_page_config(**PAGE_CONFIG)

    # Apply custom CSS
    st.markdown(get_custom_css(), unsafe_allow_html=True)

    # Initialize session state
    StateManager.initialize()

    # Start a new conversation if none exists
    if not st.session_state.current_conversation_id:
        StateManager.create_new_conversation()

    # Render sidebar
    render_sidebar()

    # Display chat messages (show first so modal appears on top)
    render_chat_messages()

    # Render documents list modal (after chat so it appears on top)
    render_documents_modal()

    # File upload component
    render_file_upload()

    # Chat input
    handle_chat_input()

    # System status indicator
    render_system_status()


if __name__ == "__main__":
    main()