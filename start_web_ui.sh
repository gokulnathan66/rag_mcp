#!/bin/bash

# RAG MCP Server Web UI Startup Script

set -e

echo "=================================="
echo "RAG MCP Server Web UI"
echo "=================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker and try again"
    exit 1
fi

# Check if Qdrant is running
echo "🔍 Checking Qdrant status..."
if ! docker ps | grep -q qdrant; then
    echo "📦 Starting Qdrant vector database..."
    docker-compose up -d qdrant
    echo "⏳ Waiting for Qdrant to be ready..."
    sleep 5
    
    # Wait for Qdrant health check
    max_attempts=30
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:6333/health > /dev/null 2>&1; then
            echo "✅ Qdrant is ready!"
            break
        fi
        attempt=$((attempt + 1))
        echo "   Waiting... ($attempt/$max_attempts)"
        sleep 1
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo "❌ Qdrant failed to start"
        exit 1
    fi
else
    echo "✅ Qdrant is already running"
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

# Check if dependencies are installed
echo ""
echo "🔍 Checking Python dependencies..."
if ! python3 -c "import fastapi, uvicorn, qdrant_client, fastembed" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
else
    echo "✅ Dependencies are installed"
fi

# Create data directory
mkdir -p data/uploads
echo "✅ Data directory ready"

echo ""
echo "=================================="
echo "🚀 Starting Web UI Server..."
echo "=================================="
echo ""
echo "Access the UI at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the web server
python3 -m app.web_server
