"""
Chat component for message display and interaction
"""
import streamlit as st
from utils.api_client import api_client
from utils.state_manager import StateManager
from config.settings import MESSAGE_PREVIEW_LENGTH


def display_sources(sources):
    """Display sources in an expander"""
    with st.expander("📚 Kaynaklar"):
        for i, source in enumerate(sources, 1):
            st.write(f"**Kaynak {i}:**")
            doc_name = source.get('document_name', source.get('document_id', 'Bilinmeyen'))
            doc_url = source.get('document_url', '')
            page_num = source.get('page_number', 'N/A')
            text_preview = source.get('text', '')[:MESSAGE_PREVIEW_LENGTH] + '...' if source.get('text') else ''
            score = source.get('score', 0.0)

            st.write(f"📄 Doküman: {doc_name}")
            if doc_url:
                st.write(f"🔗 [Dokümanı Görüntüle]({doc_url})")
            st.write(f"📑 Sayfa: {page_num}")
            if text_preview:
                st.write(f"📝 İçerik: *{text_preview}*")
            st.write(f"⭐ Skor: {score:.3f}")
            st.write("---")


def render_chat_messages():
    """Render all chat messages"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Show sources if available
            if "sources" in message and message["sources"]:
                display_sources(message["sources"])


def handle_chat_input():
    """Handle chat input and response"""
    if prompt := st.chat_input("Sorunuzu yazın...", disabled=st.session_state.processing_query):
        # Add user message
        StateManager.add_message("user", prompt)

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Düşünüyorum..."):
                st.session_state.processing_query = True

                # Query the API
                response = api_client.query(prompt)

                if "error" in response:
                    assistant_response = f"❌ Hata: {response['error']}"
                    sources = []
                else:
                    assistant_response = response.get("answer", "Üzgünüm, bu soruya cevap veremedim.")
                    sources = response.get("sources", [])

                # Display response
                st.markdown(assistant_response)

                # Display sources if available
                if sources:
                    display_sources(sources)

                # Add assistant message with sources
                StateManager.add_message("assistant", assistant_response, sources)
                st.session_state.processing_query = False

        st.rerun()