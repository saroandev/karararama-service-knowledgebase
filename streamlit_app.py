import streamlit as st
import requests
import json
from datetime import datetime
import time
import os

# Page config
st.set_page_config(
    page_title="RAG Chat Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Simple CSS using sidebar colors
st.markdown("""
<style>
    .chat-message {
        background-color: #262730;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 4px solid #262730;
    }
    
    .source-box {
        background-color: #262730;
        border: 1px solid #262730;
        border-radius: 5px;
        padding: 0.8rem;
        margin: 0.5rem 0;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# API Base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []

# Header
# Header - Use Streamlit native components
st.title("📚 OneDocs Assistant")
st.markdown("### Upload PDFs and ask questions about your documents")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("📄 Document Management")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload PDF documents to ask questions about them"
    )
    
    if uploaded_file is not None:
        if st.button("📤 Upload & Process", type="primary"):
            with st.spinner("Processing document..."):
                try:
                    # Prepare file for upload
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    
                    # Upload to RAG API
                    response = requests.post(f"{API_BASE_URL}/ingest", files=files)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Document processed successfully!")
                        st.json(result)
                        
                        # Add to uploaded files
                        if uploaded_file.name not in st.session_state.uploaded_files:
                            st.session_state.uploaded_files.append(uploaded_file.name)
                        
                    else:
                        st.error(f"❌ Upload failed: {response.text}")
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Show uploaded files
    if st.session_state.uploaded_files:
        st.subheader("📚 Uploaded Documents")
        for file in st.session_state.uploaded_files:
            st.write(f"✅ {file}")
    
    # System status
    st.subheader("🔧 System Status")
    if st.button("Check Health"):
        try:
            response = requests.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                health_data = response.json()
                st.success("✅ System Healthy")
                st.json(health_data)
            else:
                st.error("❌ System Unhealthy")
        except:
            st.error("❌ Cannot connect to API")
    
    # Clear chat
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Main chat area
st.header("💬 Chat")

# Display chat messages
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="chat-message">
            <strong>You:</strong><br>
            {message["content"]}
            <div style="text-align: right; font-size: 0.8em; color: #666;">
                {message.get("timestamp", "")}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    else:  # bot message
        st.markdown(f"""
        <div class="chat-message">
            <strong>📚 Assistant:</strong><br>
            {message["content"]}
        """, unsafe_allow_html=True)
        
        # Show sources if available
        if "sources" in message and message["sources"]:
            st.markdown("**📖 Sources:**")
            for i, source in enumerate(message["sources"], 1):
                st.markdown(f"""
                <div class="source-box">
                    <strong>Source {i}:</strong> {source.get('document_title', 'Unknown')} 
                    (Page {source.get('page_number', '?')}, Score: {source.get('score', 0):.2f})<br>
                    <em>"{source.get('text_preview', '')[:200]}..."</em>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="text-align: right; font-size: 0.8em; color: #666;">
                {message.get("timestamp", "")}
            </div>
        </div>
        """, unsafe_allow_html=True)

# Chat input
user_question = st.chat_input("Ask a question about your documents...")

if user_question:
    # Add user message
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.messages.append({
        "role": "user",
        "content": user_question,
        "timestamp": timestamp
    })
    
    # Show user message immediately
    st.experimental_rerun()

# Process user question
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_message = st.session_state.messages[-1]
    
    with st.spinner("🤔 Thinking..."):
        try:
            # Query RAG API
            query_data = {
                "question": last_message["content"],
                "top_k": 5
            }
            
            response = requests.post(f"{API_BASE_URL}/query", json=query_data)
            
            if response.status_code == 200:
                result = response.json()
                
                # Add bot response
                bot_message = {
                    "role": "bot",
                    "content": result.get("answer", "Sorry, I couldn't generate an answer."),
                    "sources": result.get("sources", []),
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                
                st.session_state.messages.append(bot_message)
                
            else:
                # Add error message
                st.session_state.messages.append({
                    "role": "bot",
                    "content": f"❌ Error: {response.text}",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
        
        except Exception as e:
            # Add error message
            st.session_state.messages.append({
                "role": "bot",
                "content": f"❌ Connection error: {str(e)}",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
    
    # Rerun to show the bot response
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9em;">
    <p>🚀 OneDocs Assistant powered by Milvus, MinIO & OpenAI</p>
    <p>Upload PDF documents and ask questions to get AI-powered answers with source citations.</p>
</div>
""", unsafe_allow_html=True)