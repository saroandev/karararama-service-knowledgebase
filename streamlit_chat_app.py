import streamlit as st
import requests
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

# Page configuration
st.set_page_config(
    page_title="RAG Chat Assistant",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern appearance
st.markdown("""
<style>
    /* Main chat container */
    .main > div {
        padding-top: 2rem;
    }

    /* Chat messages */
    .stChatMessage {
        background-color: transparent;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
    }

    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255, 255, 255, 0.1);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.2);
        transition: all 0.3s ease;
        margin: 2px 0;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255, 255, 255, 0.2);
        border-color: rgba(255, 255, 255, 0.4);
        transform: translateX(2px);
    }

    /* Top sidebar buttons (smaller) */
    .sidebar-top-buttons .stButton > button {
        height: 2rem !important;
        font-size: 0.875rem !important;
        padding: 0.25rem 0.5rem !important;
        margin: 2px 0 !important;
    }

    /* Modern button styling */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 2.5rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    /* File upload button styling */
    section[data-testid="stFileUploader"] {
        position: fixed;
        bottom: 70px;
        left: 50%;
        transform: translateX(-280px);
        z-index: 999;
        width: 40px;
    }
    
    section[data-testid="stFileUploader"] > div {
        background: transparent !important;
        border: none !important;
    }
    
    section[data-testid="stFileUploader"] button {
        background: #667eea !important;
        border-radius: 50% !important;
        width: 40px !important;
        height: 40px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* Modern chat input */
    .stChatInput > div {
        background: #f1f3f5 !important;
        border: 2px solid #dee2e6 !important;
        border-radius: 12px !important;
    }
    
    .stChatInput > div:focus-within {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* Scrollable conversation history */
    .conversation-history {
        max-height: calc(100vh - 300px);
        overflow-y: auto;
        padding-bottom: 120px;
    }

    /* Bottom sidebar section */
    .sidebar-bottom {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 21rem;
        background: #2c3e50;
        padding: 1rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        z-index: 1000;
    }

    /* System status indicator */
    .system-status {
        position: fixed;
        bottom: 75px;
        left: 365px;
        z-index: 1001;
        font-size: 0.75rem;
        background: transparent;
    }

    /* Documents list styling */
    .documents-list-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 1rem;
        border-radius: 8px;
        background: rgba(0, 0, 0, 0.02);
    }
    
    /* Conversation item */
    .conversation-item {
        padding: 0.5rem;
        margin: 0.25rem 0;
        border-radius: 8px;
        cursor: pointer;
        background: rgba(255, 255, 255, 0.05);
    }
    
    .conversation-item:hover {
        background: rgba(255, 255, 255, 0.1);
    }
    
    /* Hide sidebar text in markdown */
    section[data-testid="stSidebar"] .stMarkdown {
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
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

    if 'show_settings' not in st.session_state:
        st.session_state.show_settings = False

    if 'sidebar_collapsed' not in st.session_state:
        st.session_state.sidebar_collapsed = False

    if 'processing_query' not in st.session_state:
        st.session_state.processing_query = False

    if 'show_documents_list' not in st.session_state:
        st.session_state.show_documents_list = False

    if 'knowledge_base_documents' not in st.session_state:
        st.session_state.knowledge_base_documents = []

    if 'document_search_query' not in st.session_state:
        st.session_state.document_search_query = ""

init_session_state()

# Helper functions
def create_new_conversation():
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

def load_conversation(conversation_id):
    for conv in st.session_state.conversations:
        if conv['id'] == conversation_id:
            st.session_state.current_conversation_id = conversation_id
            st.session_state.messages = conv['messages']
            break

def save_current_conversation():
    if st.session_state.current_conversation_id:
        for conv in st.session_state.conversations:
            if conv['id'] == st.session_state.current_conversation_id:
                conv['messages'] = st.session_state.messages
                # Update title based on first message
                if st.session_state.messages and len(st.session_state.messages) > 0:
                    first_user_msg = next((msg['content'] for msg in st.session_state.messages if msg['role'] == 'user'), None)
                    if first_user_msg:
                        conv['title'] = first_user_msg[:30] + "..." if len(first_user_msg) > 30 else first_user_msg
                break

def upload_file_sync(file):
    """Synchronously upload a file"""
    try:
        # Prepare request
        files = {"file": (file.name, file.getvalue(), file.type or "application/pdf")}

        # Send to API
        response = requests.post(
            f"{API_BASE_URL}/ingest",
            files=files,
            timeout=300
        )

        if response.status_code == 200:
            result = response.json()

            # Handle different response types based on status
            if "chunks_created" in result:
                # Successful new document
                st.session_state.uploaded_documents.append({
                    'filename': file.name,
                    'document_id': result.get('document_id'),
                    'chunks': result.get('chunks_created', 0),
                    'upload_time': datetime.now().isoformat()
                })
                return True, file.name, result
            elif "chunks_count" in result:
                # Document already exists
                return True, file.name, {"message": "Doküman zaten mevcut", "existing": True}
            else:
                return False, file.name, result.get('message', 'Bilinmeyen hata')
        else:
            return False, file.name, f"HTTP {response.status_code}: {response.text}"

    except Exception as e:
        return False, file.name, str(e)

def query_api(question: str, use_reranker: bool = True, top_k: int = 5):
    """Send query to API"""
    try:
        payload = {
            "question": question,
            "top_k": top_k,
            "use_reranker": use_reranker
        }

        response = requests.post(
            f"{API_BASE_URL}/query",
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API Error: {response.status_code}"}

    except Exception as e:
        return {"error": str(e)}

def fetch_documents():
    """Fetch all documents from knowledge base"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/documents",
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Dokümanlar yüklenemedi: HTTP {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Dokümanlar yüklenemedi: {str(e)}")
        return []

def delete_document(document_id: str):
    """Delete a document from knowledge base"""
    try:
        response = requests.delete(
            f"{API_BASE_URL}/documents/{document_id}",
            timeout=10
        )
        return response.status_code == 200, response.json() if response.status_code == 200 else response.text
    except Exception as e:
        return False, str(e)

# Sidebar
with st.sidebar:
    # Top buttons container with smaller buttons
    st.markdown('<div class="sidebar-top-buttons">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Yeni", use_container_width=True, key="new_conv"):
            create_new_conversation()
            st.rerun()

    with col2:
        if st.button("✖" if not st.session_state.sidebar_collapsed else "☰", use_container_width=True, key="toggle_sidebar"):
            st.session_state.sidebar_collapsed = not st.session_state.sidebar_collapsed
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Scrollable conversation history
    st.markdown('<div class="conversation-history">', unsafe_allow_html=True)
    st.markdown("### Konuşma Geçmişi")

    if st.session_state.conversations:
        for conv in reversed(st.session_state.conversations):
            conv_date = datetime.fromisoformat(conv['created_at']).strftime("%d/%m %H:%M")
            if st.button(f"💬 {conv['title']}\n_{conv_date}_", key=conv['id'], use_container_width=True):
                load_conversation(conv['id'])
                st.rerun()
    else:
        st.info("Henüz konuşma yok")
    st.markdown('</div>', unsafe_allow_html=True)

    # Fixed bottom section
    st.markdown('<div class="sidebar-bottom">', unsafe_allow_html=True)

    # Uploaded documents info
    if st.session_state.uploaded_documents:
        with st.expander(f"📄 Yüklü Dokümanlar ({len(st.session_state.uploaded_documents)})"):
            for doc in st.session_state.uploaded_documents:
                st.write(f"• {doc['filename']} ({doc['chunks']} chunk)")

    # List Documents button
    if st.button("📚 Dokümanları Listele", use_container_width=True, key="list_docs_btn"):
        st.session_state.show_documents_list = True
        st.session_state.knowledge_base_documents = fetch_documents()

    # User and Settings buttons at bottom
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👤", use_container_width=True, help="Kullanıcı", key="user_btn"):
            st.session_state.show_user_profile = True

    with col2:
        if st.button("⚙️", use_container_width=True, help="Ayarlar", key="settings_btn"):
            st.session_state.show_settings = not st.session_state.show_settings
    st.markdown('</div>', unsafe_allow_html=True)

# Settings Modal
if st.session_state.show_settings:
    with st.expander("⚙️ Ayarlar", expanded=True):
        st.markdown("### API Ayarları")
        st.text_input("API URL", value=API_BASE_URL, disabled=True)

        st.markdown("### Sorgu Ayarları")
        default_top_k = st.slider("Varsayılan sonuç sayısı (top_k)", 1, 20, 5)
        use_reranker = st.checkbox("Reranker kullan", value=True)

        st.markdown("### Görünüm")
        dark_mode = st.checkbox("Karanlık Mod", value=False)

        if st.button("Kaydet", type="primary"):
            st.session_state.show_settings = False
            st.rerun()

# Documents List Modal
if st.session_state.show_documents_list:
    with st.container():
        st.markdown("---")
        col1, col2 = st.columns([8, 2])

        with col1:
            st.markdown("### 📚 Knowledge Base Dokümanları")

        with col2:
            button_cols = st.columns(3)
            with button_cols[0]:
                if st.button("🔄", help="Yenile", key="refresh_docs"):
                    st.session_state.knowledge_base_documents = fetch_documents()
                    st.rerun()
            with button_cols[1]:
                if st.button("❌", help="Kapat", key="close_docs"):
                    st.session_state.show_documents_list = False
                    st.rerun()

        # Search input
        search_col1, search_col2 = st.columns([10, 1])
        with search_col1:
            search_query = st.text_input(
                "🔍 Doküman Ara",
                value=st.session_state.document_search_query,
                placeholder="Doküman adını yazın...",
                key="doc_search_input",
                label_visibility="collapsed"
            )
            st.session_state.document_search_query = search_query

        if st.session_state.knowledge_base_documents:
            # Sort documents: numbers first, then alphabetically
            sorted_docs = sorted(
                st.session_state.knowledge_base_documents,
                key=lambda x: (
                    not x.get('title', '').replace('.pdf', '')[0].isdigit() if x.get('title', '') else True,
                    x.get('title', '').lower().replace('.pdf', '')
                )
            )

            # Filter documents based on search query
            if search_query:
                filtered_docs = [
                    doc for doc in sorted_docs
                    if search_query.lower() in doc.get('title', '').lower()
                ]
            else:
                filtered_docs = sorted_docs

            st.info(f"📊 Toplam {len(filtered_docs)} / {len(st.session_state.knowledge_base_documents)} doküman gösteriliyor")

            # Create a table-like view
            for idx, doc in enumerate(filtered_docs):
                with st.container():
                    col1, col2, col3, col4 = st.columns([4, 2, 2, 1])

                    with col1:
                        st.write(f"📄 **{doc.get('title', 'Bilinmeyen')}**")
                        # Show URL if available, otherwise show "URL bulunamadı"
                        doc_url = doc.get('url')
                        if doc_url:
                            st.caption(f"🔗 [İndir]({doc_url})")
                        else:
                            st.caption("🔗 URL bulunamadı")

                    with col2:
                        st.write(f"📦 {doc.get('chunks_count', 0)} parça")

                    with col3:
                        created_at = doc.get('created_at', '')
                        if created_at:
                            try:
                                date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
                                st.write(f"📅 {formatted_date}")
                            except:
                                st.write(f"📅 {created_at[:10]}")

                    with col4:
                        if st.button("🗑️", key=f"del_{doc.get('document_id')}", help="Sil"):
                            doc_id = doc.get('document_id')
                            doc_title = doc.get('title', 'Bilinmeyen')

                            with st.spinner(f"'{doc_title}' siliniyor..."):
                                success, result = delete_document(doc_id)

                                if success:
                                    st.success(f"✅ '{doc_title}' başarıyla silindi!")
                                    # Refresh the list
                                    st.session_state.knowledge_base_documents = fetch_documents()
                                    st.rerun()
                                else:
                                    st.error(f"❌ Silme başarısız: {result}")

                st.markdown("---")
        else:
            st.warning("📭 Knowledge base'de henüz doküman bulunmuyor.")
            st.info("💡 PDF yüklemek için sol taraftaki dosya yükleme butonunu kullanabilirsiniz.")

# Main chat area
main_container = st.container()

# Start a new conversation if none exists
if not st.session_state.current_conversation_id:
    create_new_conversation()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Show sources if available
        if "sources" in message and message["sources"]:
            with st.expander("📚 Kaynaklar"):
                for i, source in enumerate(message["sources"], 1):
                    st.write(f"**Kaynak {i}:**")
                    doc_name = source.get('document_name', source.get('document_id', 'Bilinmeyen'))
                    doc_url = source.get('document_url', '')
                    page_num = source.get('page_number', 'N/A')
                    text_preview = source.get('text', '')[:150] + '...' if source.get('text') else ''
                    score = source.get('score', 0.0)
                    
                    st.write(f"📄 Doküman: {doc_name}")
                    if doc_url:
                        st.write(f"🔗 [Dokümanı Görüntüle]({doc_url})")
                    st.write(f"📑 Sayfa: {page_num}")
                    if text_preview:
                        st.write(f"📝 İçerik: *{text_preview}*")
                    st.write(f"⭐ Skor: {score:.3f}")
                    st.write("---")

# File upload button - minimal design
uploaded_files = st.file_uploader(
    "📎",
    accept_multiple_files=True,
    type=['pdf', 'txt', 'docx', 'md', 'html'],
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
                success, filename, result = upload_file_sync(file)

                if success:
                    if isinstance(result, dict) and result.get("existing"):
                        st.info(f"ℹ️ {filename} zaten mevcut")
                    else:
                        chunks = result.get('chunks_created', 0) if isinstance(result, dict) else 0
                        st.success(f"✅ {filename} başarıyla yüklendi ({chunks} parça)")
                else:
                    st.error(f"❌ {filename} yüklenemedi: {result}")

# Chat input at the bottom
if prompt := st.chat_input("Sorunuzu yazın...", disabled=st.session_state.processing_query):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get assistant response
    with st.chat_message("assistant"):
        with st.spinner("Düşünüyorum..."):
            st.session_state.processing_query = True
            
            # Query the API
            response = query_api(prompt)
            
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
                with st.expander("📚 Kaynaklar"):
                    for i, source in enumerate(sources, 1):
                        st.write(f"**Kaynak {i}:**")
                        doc_name = source.get('document_name', source.get('document_id', 'Bilinmeyen'))
                        doc_url = source.get('document_url', '')
                        page_num = source.get('page_number', 'N/A')
                        text_preview = source.get('text', '')[:150] + '...' if source.get('text') else ''
                        score = source.get('score', 0.0)
                        
                        st.write(f"📄 Doküman: {doc_name}")
                        if doc_url:
                            st.write(f"🔗 [Dokümanı Görüntüle]({doc_url})")
                        st.write(f"📑 Sayfa: {page_num}")
                        if text_preview:
                            st.write(f"📝 İçerik: *{text_preview}*")
                        st.write(f"⭐ Skor: {score:.3f}")
                        st.write("---")
            
            # Add assistant message with sources
            message_data = {"role": "assistant", "content": assistant_response}
            if sources:
                message_data["sources"] = sources
            
            st.session_state.messages.append(message_data)
            st.session_state.processing_query = False
    
    # Save conversation
    save_current_conversation()
    st.rerun()

# System health indicator (near chat input)
st.markdown('<div class="system-status">', unsafe_allow_html=True)
try:
    health_response = requests.get(f"{API_BASE_URL}/health", timeout=2)
    if health_response.status_code == 200:
        st.markdown("🟢")
    else:
        st.markdown("🔴")
except:
    st.markdown("🔴")
st.markdown('</div>', unsafe_allow_html=True)