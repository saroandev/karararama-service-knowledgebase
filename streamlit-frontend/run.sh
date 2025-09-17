#!/bin/bash

# Run the modular Streamlit application
echo "Starting RAG Chat Assistant..."

# Set Python path to include parent directory
export PYTHONPATH="${PYTHONPATH}:$(dirname $(pwd))"

# Run streamlit app
streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --theme.base "light"