#!/bin/bash

# FastAPI Development Server Startup Script

echo "🚀 Starting FastAPI Development Server..."

# Set Python path
export PYTHONPATH=/Users/ugur/Desktop/Onedocs-RAG-Project/main

# Load environment variables from .env file
if [ -f "/Users/ugur/Desktop/Onedocs-RAG-Project/main/.env" ]; then
    export $(cat /Users/ugur/Desktop/Onedocs-RAG-Project/main/.env | grep -v '^#' | xargs)
    echo "✅ Environment variables loaded from .env"
fi

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

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python -c "import fastapi; import uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ Missing dependencies. Installing requirements..."
    pip install -r requirements.txt
fi

# Display environment configuration
echo ""
echo "📋 Configuration:"
echo "  - PYTHONPATH: $PYTHONPATH"
echo "  - API URL: http://localhost:8080"
echo "  - Auto-reload: Enabled"
echo ""

# Start uvicorn with auto-reload for development
echo "🌐 Starting server at http://localhost:8080"
echo "📖 API Documentation: http://localhost:8080/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Run production server
python production_server.py