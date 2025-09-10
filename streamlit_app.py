import streamlit as st
import requests
import os
from typing import Optional
import json

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

st.set_page_config(
    page_title="RAG Pipeline Interface",
    page_icon="📚",
    layout="wide"
)

st.title("📚 RAG Pipeline Interface")
st.markdown("---")

# Create tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["📤 Document Upload", "🔍 Query", "🏥 System Health"])

# Document Upload Tab
with tab1:
    st.header("Upload PDF Document")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a PDF document to process and index"
    )
    
    if uploaded_file is not None:
        st.write(f"📄 Selected file: {uploaded_file.name}")
        st.write(f"📏 File size: {uploaded_file.size:,} bytes")
        
        if st.button("🚀 Process Document", type="primary"):
            with st.spinner("Processing document..."):
                try:
                    # Send file to API
                    files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                    response = requests.post(
                        f"{API_BASE_URL}/ingest",
                        files=files,
                        timeout=300  # 5 minutes timeout for large files
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success("✅ Document processed successfully!")
                        
                        # Display processing details
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Chunks", result.get("total_chunks", "N/A"))
                        with col2:
                            st.metric("Pages Processed", result.get("pages_processed", "N/A"))
                        with col3:
                            st.metric("Status", result.get("status", "N/A"))
                        
                        # Show detailed results
                        with st.expander("📊 Processing Details"):
                            st.json(result)
                    else:
                        st.error(f"❌ Error: {response.status_code}")
                        if response.text:
                            st.error(response.text)
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Connection error: {str(e)}")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {str(e)}")

# Query Tab
with tab2:
    st.header("Query Documents")
    
    # Query input
    query = st.text_area(
        "Enter your question:",
        placeholder="Ask a question about the documents...",
        height=100
    )
    
    # Advanced options
    with st.expander("⚙️ Advanced Options"):
        col1, col2 = st.columns(2)
        with col1:
            top_k = st.slider("Number of results (top_k)", 1, 20, 5)
        with col2:
            use_reranker = st.checkbox("Use Reranker", value=True)
    
    if st.button("🔍 Search", type="primary", disabled=not query):
        with st.spinner("Searching..."):
            try:
                # Prepare request payload
                payload = {
                    "question": query,
                    "top_k": top_k,
                    "use_reranker": use_reranker
                }
                
                # Send query to API
                response = requests.post(
                    f"{API_BASE_URL}/query",
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Display answer
                    st.markdown("### 💡 Answer")
                    st.write(result.get("answer", "No answer found"))
                    
                    # Display sources
                    if "sources" in result and result["sources"]:
                        st.markdown("### 📚 Sources")
                        for i, source in enumerate(result["sources"], 1):
                            with st.expander(f"Source {i}: {source.get('metadata', {}).get('source', 'Unknown')}"):
                                st.write(f"**Content:** {source.get('content', '')}")
                                st.write(f"**Score:** {source.get('score', 'N/A')}")
                                if "metadata" in source:
                                    st.write("**Metadata:**")
                                    st.json(source["metadata"])
                    
                    # Show raw response
                    with st.expander("🔧 Raw Response"):
                        st.json(result)
                else:
                    st.error(f"❌ Error: {response.status_code}")
                    if response.text:
                        st.error(response.text)
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Connection error: {str(e)}")
            except Exception as e:
                st.error(f"❌ Unexpected error: {str(e)}")

# System Health Tab
with tab3:
    st.header("System Health Check")
    
    if st.button("🔄 Check Health"):
        with st.spinner("Checking system health..."):
            try:
                # Check API health
                response = requests.get(f"{API_BASE_URL}/health", timeout=10)
                
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Overall status
                    status = health_data.get("status", "unknown")
                    if status == "healthy":
                        st.success("✅ System is healthy")
                    else:
                        st.warning(f"⚠️ System status: {status}")
                    
                    # Service details
                    st.markdown("### Service Status")
                    services = health_data.get("services", {})
                    
                    cols = st.columns(len(services))
                    for i, (service, status) in enumerate(services.items()):
                        with cols[i]:
                            if status == "connected":
                                st.success(f"✅ {service.upper()}")
                            else:
                                st.error(f"❌ {service.upper()}")
                    
                    # Show detailed health info
                    with st.expander("📊 Detailed Health Information"):
                        st.json(health_data)
                else:
                    st.error(f"❌ Health check failed: {response.status_code}")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Cannot connect to API: {str(e)}")
                st.info("Make sure the FastAPI server is running at " + API_BASE_URL)

# Sidebar with information
with st.sidebar:
    st.markdown("## 📖 About")
    st.markdown("""
    This is a RAG (Retrieval-Augmented Generation) pipeline interface.
    
    **Features:**
    - Upload and process PDF documents
    - Query indexed documents
    - View system health status
    
    **API Endpoint:** `{}`
    """.format(API_BASE_URL))
    
    st.markdown("---")
    st.markdown("### 🔗 Quick Links")
    st.markdown(f"- [API Documentation]({API_BASE_URL}/docs)")
    st.markdown("- [MinIO Console](http://localhost:9001)")
    st.markdown("- [Milvus Attu](http://localhost:8000)")
    
    st.markdown("---")
    st.markdown("### ⚙️ Configuration")
    st.code(f"""
API URL: {API_BASE_URL}
    """, language="text")