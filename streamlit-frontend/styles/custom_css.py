"""
Custom CSS styles for the application
"""

def get_custom_css() -> str:
    """Return custom CSS styles"""
    return """
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
    """