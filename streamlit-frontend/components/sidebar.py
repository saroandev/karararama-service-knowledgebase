"""
Sidebar component for the application
"""
import streamlit as st
from datetime import datetime
from utils.state_manager import StateManager
from utils.api_client import api_client


def render_sidebar():
    """Render the sidebar with all its components"""
    with st.sidebar:
        # Top buttons container with smaller buttons
        st.markdown('<div class="sidebar-top-buttons">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Yeni", use_container_width=True, key="new_conv"):
                StateManager.create_new_conversation()
                st.rerun()

        with col2:
            if st.button("✖" if not st.session_state.sidebar_collapsed else "☰",
                        use_container_width=True, key="toggle_sidebar"):
                st.session_state.sidebar_collapsed = not st.session_state.sidebar_collapsed
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # Conversation history (without title)
        if st.session_state.conversations:
            for conv in reversed(st.session_state.conversations):
                conv_date = datetime.fromisoformat(conv['created_at']).strftime("%d/%m %H:%M")
                if st.button(f"💬 {conv['title']}\n_{conv_date}_",
                           key=conv['id'], use_container_width=True):
                    StateManager.load_conversation(conv['id'])
                    st.rerun()
        else:
            st.info("Henüz konuşma yok")

        # Bottom section - only documents
        st.markdown("---")

        # Uploaded documents info
        if st.session_state.uploaded_documents:
            with st.expander(f"📄 Yüklü Dokümanlar ({len(st.session_state.uploaded_documents)})"):
                for doc in st.session_state.uploaded_documents:
                    st.write(f"• {doc['filename']} ({doc['chunks']} chunk)")

        # List Documents button
        if st.button("📚 Dokümanları Listele", use_container_width=True, key="list_docs_btn"):
            st.session_state.show_documents_list = not st.session_state.show_documents_list
            if st.session_state.show_documents_list:
                st.session_state.knowledge_base_documents = api_client.fetch_documents()