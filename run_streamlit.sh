#!/bin/bash

# Streamlit Chat Interface Startup Script

echo "💬 Starting RAG Chat Interface..."

# Set API base URL
export API_BASE_URL=http://localhost:8080

# Activate virtual environment
source venv/bin/activate

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

# Display Python and pip versions
echo "📦 Python version: $(python --version)"
echo "📦 Pip version: $(pip --version)"

# Check if streamlit is installed
echo "🔍 Checking dependencies..."
python -c "import streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ Streamlit not found. Installing..."
    pip install streamlit
fi

# Check if python-dotenv is installed
python -c "import dotenv" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ python-dotenv not found. Installing..."
    pip install python-dotenv
fi

# Display environment configuration
echo ""
echo "📋 Configuration:"
echo "  - API_BASE_URL: $API_BASE_URL"
echo "  - Chat Interface URL: http://localhost:8501"
echo "  - Interface Type: ChatGPT-like UI"
echo ""

# Check if FastAPI is running
echo "🔍 Checking FastAPI connection..."
curl -s -o /dev/null -w "FastAPI Status: %{http_code}\n" http://localhost:8080/health
if [ $? -ne 0 ]; then
    echo "⚠️ Warning: FastAPI server might not be running at http://localhost:8080"
    echo "   Please ensure FastAPI is running before using the chat interface"
fi

echo ""
echo "🌐 Starting Chat Interface at http://localhost:8501"
echo "💡 Features:"
echo "   • ChatGPT-like interface"
echo "   • Multi-file upload support"
echo "   • Conversation history"
echo "   • Auto-ingest on file upload"
echo ""
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Run streamlit with the new chat app
streamlit run streamlit_chat_app.py --server.port=8501 --server.address=0.0.0.0