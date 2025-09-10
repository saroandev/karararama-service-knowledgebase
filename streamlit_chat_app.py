import streamlit as st
import requests
import os
import json
import asyncio
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
        margin: 4px 0;
    }
    
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255, 255, 255, 0.2);
        border-color: rgba(255, 255, 255, 0.4);
        transform: translateX(2px);
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
    
    /* Bottom sidebar section */
    .sidebar-bottom {
        position: fixed;
        bottom: 0;
        width: inherit;
        background: linear-gradient(180deg, transparent 0%, #2c3e50 20%);
        padding: 1rem;
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
    
    if 'uploading_files' not in st.session_state:
        st.session_state.uploading_files = set()
    
    if 'uploaded_documents' not in st.session_state:
        st.session_state.uploaded_documents = []
    
    if 'show_settings' not in st.session_state:
        st.session_state.show_settings = False
    
    if 'sidebar_collapsed' not in st.session_state:
        st.session_state.sidebar_collapsed = False
    
    if 'processing_query' not in st.session_state:
        st.session_state.processing_query = False

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

async def upload_file_async(file, file_index):
    """Asynchronously upload a file"""
    try:
        # Add to uploading set
        st.session_state.uploading_files.add(file.name)
        
        # Determine file type and prepare request
        files = {"file": (file.name, file, file.type or "application/octet-stream")}
        
        # Send to API
        response = requests.post(
            f"{API_BASE_URL}/ingest",
            files=files,
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            st.session_state.uploaded_documents.append({
                'filename': file.name,
                'document_id': result.get('document_id'),
                'chunks': result.get('chunks_created', 0),
                'upload_time': datetime.now().isoformat()
            })
            return True, file.name, result
        else:
            return False, file.name, response.text
            
    except Exception as e:
        return False, file.name, str(e)
    finally:
        # Remove from uploading set
        st.session_state.uploading_files.discard(file.name)

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

# Sidebar
with st.sidebar:
    # Top buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yeni Konuşma", use_container_width=True):
            create_new_conversation()
            st.rerun()
    
    with col2:
        if st.button("✖" if not st.session_state.sidebar_collapsed else "☰", use_container_width=True):
            st.session_state.sidebar_collapsed = not st.session_state.sidebar_collapsed
            st.rerun()
    
    st.markdown("---")
    
    # Conversation history
    st.markdown("### Konuşma Geçmişi")
    
    if st.session_state.conversations:
        for conv in reversed(st.session_state.conversations):
            conv_date = datetime.fromisoformat(conv['created_at']).strftime("%d/%m %H:%M")
            if st.button(f"💬 {conv['title']}\n_{conv_date}_", key=conv['id'], use_container_width=True):
                load_conversation(conv['id'])
                st.rerun()
    else:
        st.info("Henüz konuşma yok")
    
    # Spacer to push buttons to bottom
    st.markdown("<div style='flex: 1;'></div>", unsafe_allow_html=True)
    
    # Bottom section with user and settings
    st.markdown("---")
    
    # Uploaded documents info
    if st.session_state.uploaded_documents:
        with st.expander(f"📄 Yüklü Dokümanlar ({len(st.session_state.uploaded_documents)})"):
            for doc in st.session_state.uploaded_documents:
                st.write(f"• {doc['filename']} ({doc['chunks']} chunk)")
    
    # User and Settings buttons at bottom
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👤", use_container_width=True, help="Kullanıcı"):
            st.session_state.show_user_profile = True
    
    with col2:
        if st.button("⚙️", use_container_width=True, help="Ayarlar"):
            st.session_state.show_settings = not st.session_state.show_settings

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
                for source in message["sources"]:
                    st.write(f"• {source.get('metadata', {}).get('source', 'Unknown')}")

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
    for file in uploaded_files:
        if file.name not in st.session_state.uploading_files:
            # Start async upload
            with st.spinner(f"📤 {file.name} yükleniyor..."):
                success, filename, result = asyncio.run(upload_file_async(file, len(uploaded_files)))
                
                if success:
                    st.success(f"✅ {filename} başarıyla yüklendi!")
                    # Add system message about upload
                    upload_msg = f"📄 **{filename}** dosyası yüklendi.\n"
                    upload_msg += f"• Document ID: {result.get('document_id')}\n"
                    upload_msg += f"• {result.get('chunks_created')} chunk oluşturuldu\n"
                    upload_msg += f"• İşlem süresi: {result.get('processing_time', 0):.2f} saniye"
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": upload_msg
                    })
                    save_current_conversation()
                else:
                    st.error(f"❌ {filename} yüklenemedi: {result}")
    
    # Clear the file uploader
    st.rerun()

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
                        st.write(f"• İçerik: {source.get('content', '')[:200]}...")
                        st.write(f"• Skor: {source.get('score', 'N/A')}")
            
            # Add assistant message with sources
            message_data = {"role": "assistant", "content": assistant_response}
            if sources:
                message_data["sources"] = sources
            
            st.session_state.messages.append(message_data)
            st.session_state.processing_query = False
    
    # Save conversation
    save_current_conversation()
    st.rerun()

# System health indicator (bottom right corner)
with st.container():
    col1, col2, col3 = st.columns([8, 1, 1])
    with col3:
        try:
            health_response = requests.get(f"{API_BASE_URL}/health", timeout=2)
            if health_response.status_code == 200:
                st.success("🟢 Sistem Aktif")
            else:
                st.error("🔴 Sistem Kapalı")
        except:
            st.error("🔴 Bağlantı Yok")