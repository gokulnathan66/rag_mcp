FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for ONNX runtime and other requirements
# Add curl for health checks
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY .env.example .env
COPY docker-healthcheck.py ./

# Create data directory for CSV files
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CSV_DATA_DIRECTORY=/app/data
ENV QDRANT_URL=http://qdrant:6333

# HTTP Transport Configuration
ENV TRANSPORT_MODE=default
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8000
ENV MAX_CONCURRENT_CONNECTIONS=100
ENV CONNECTION_TIMEOUT=300
ENV REQUEST_TIMEOUT=60
ENV ENABLE_CORS=true
ENV CORS_ORIGINS=*
ENV ENABLE_HEALTH_ENDPOINT=true
ENV HEALTH_CHECK_PATH=/health

# Expose port for HTTP MCP server
EXPOSE 8000

# Add comprehensive health check using Python script
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python docker-healthcheck.py

# Run the FastMCP server
CMD ["python", "-m", "app.main"]
