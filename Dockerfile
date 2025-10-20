FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for ONNX runtime and other requirements
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY .env.example .env

# Create data directory for CSV files
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CSV_DATA_DIRECTORY=/app/data
ENV QDRANT_URL=http://qdrant:6333

# Expose port for MCP server (if needed for HTTP transport)
EXPOSE 8000

# Run the FastMCP server
CMD ["python", "-m", "app.main"]
