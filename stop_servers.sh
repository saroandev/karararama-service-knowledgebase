#!/bin/bash

echo "🛑 Stopping all servers..."

# Stop FastAPI
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null ; then
    echo "Stopping FastAPI on port 8080..."
    kill $(lsof -t -i:8080)
    echo "✅ FastAPI stopped"
else
    echo "FastAPI not running on port 8080"
fi

# Stop Streamlit
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null ; then
    echo "Stopping Streamlit on port 8501..."
    kill $(lsof -t -i:8501)
    echo "✅ Streamlit stopped"
else
    echo "Streamlit not running on port 8501"
fi

echo "🎯 All servers stopped"