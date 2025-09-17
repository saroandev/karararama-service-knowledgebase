"""
File upload component
"""
import streamlit as st
from utils.api_client import api_client
from utils.state_manager import StateManager
from config.settings import ALLOWED_FILE_TYPES


def render_file_upload():
    """Render file upload component and handle uploads"""
    uploaded_files = st.file_uploader(
        "📎",
        accept_multiple_files=True,
        type=ALLOWED_FILE_TYPES,
        key="file_uploader",
        label_visibility="collapsed",
        help="Doküman yükle"
    )

    # Auto-process uploaded files
    if uploaded_files:
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_files]

        if new_files:
            for file in new_files:
                # Mark file as processed to prevent re-upload
                st.session_state.processed_files.add(file.name)

                # Upload with spinner
                with st.spinner(f"📤 {file.name} yükleniyor..."):
                    success, filename, result = api_client.upload_document(file)

                    if success:
                        if isinstance(result, dict) and result.get("existing"):
                            st.info(f"ℹ️ {filename} zaten mevcut")
                        else:
                            chunks = result.get('chunks_created', 0) if isinstance(result, dict) else 0
                            st.success(f"✅ {filename} başarıyla yüklendi ({chunks} parça)")
                            # Add to uploaded documents
                            StateManager.add_uploaded_document(
                                filename,
                                result.get('document_id'),
                                chunks
                            )
                    else:
                        st.error(f"❌ {filename} yüklenemedi: {result}")