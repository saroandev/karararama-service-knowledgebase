"""
Application settings and configuration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

# Page Configuration
PAGE_CONFIG = {
    "page_title": "RAG Chat Assistant",
    "page_icon": "💬",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# File Upload Configuration
ALLOWED_FILE_TYPES = ['pdf', 'txt', 'docx', 'md', 'html']
MAX_FILE_SIZE_MB = 200  # 200MB limit per file

# Query Configuration
DEFAULT_TOP_K = 5
DEFAULT_USE_RERANKER = True

# UI Configuration
DOCUMENT_LIST_MAX_HEIGHT = 400  # pixels
MESSAGE_PREVIEW_LENGTH = 150  # characters