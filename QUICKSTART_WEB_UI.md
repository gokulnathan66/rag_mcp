# Quick Start Guide - Web UI

This guide will help you get the RAG MCP Server Web UI up and running in minutes.

## What You'll Get

A web interface where you can:
- 📤 Upload CSV files for indexing
- 🔍 Query documents using natural language
- 📊 View ingestion statistics
- 💚 Monitor system health

## Prerequisites

- Python 3.10+
- Docker and Docker Compose (for Qdrant)

## Quick Start (3 Steps)

### 1. Start Qdrant Vector Database

```bash
docker-compose up -d qdrant
```

Wait a few seconds for Qdrant to start, then verify:
```bash
curl http://localhost:6333/health
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Web UI

```bash
make web-ui
# or
python -m app.web_server
```

Open your browser to: **http://localhost:8000**

## Using the Web UI

### Upload a CSV File

1. Click "Choose File" in the Upload section
2. Select your CSV file
3. Click "Upload & Index"
4. Wait for processing to complete
5. View ingestion statistics (documents, chunks, embeddings)

**CSV Format Requirements:**
- Must have headers in the first row
- UTF-8 encoding (or common alternatives)
- Standard CSV format with comma delimiter

### Query Documents

1. Enter your question in natural language
2. Adjust max results (1-100)
3. Optionally set a minimum similarity score (0.0-1.0)
4. Click "Search"
5. View results with similarity scores and metadata

**Example Queries:**
- "What are the main topics discussed?"
- "Find information about pricing"
- "Show me customer feedback"

## Docker Compose (All-in-One)

To run everything with Docker:

```bash
# Start all services (Qdrant + Web UI)
docker-compose up -d

# View logs
docker-compose logs -f web-ui

# Stop all services
docker-compose down
```

Access the Web UI at: **http://localhost:8001** (note the different port)

## Architecture Flow

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────┐
│  FastAPI Server │
│  (web_api.py)   │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Orchestrator   │
│  (LangGraph)    │
└──────┬──────────┘
       │
       ├──────────────┐
       ▼              ▼
┌──────────┐   ┌──────────┐
│   CSV    │   │  Qdrant  │
│  Parser  │   │ Database │
└──────────┘   └──────────┘
       │              ▲
       ▼              │
┌──────────────────────┐
│     FastEmbed        │
│  (Embeddings)        │
└──────────────────────┘
```

## Data Flow

### Upload Flow:
1. User uploads CSV via browser
2. FastAPI saves file to `data/uploads/`
3. Orchestrator reads and parses CSV
4. Text is chunked into segments
5. FastEmbed generates vector embeddings
6. Vectors stored in Qdrant with metadata

### Query Flow:
1. User enters natural language query
2. FastEmbed converts query to vector
3. Qdrant performs similarity search
4. Results ranked by similarity score
5. Top results returned with metadata

## Configuration

Create a `.env` file to customize settings:

```bash
# CSV Configuration
CSV_DATA_DIRECTORY=./data
CSV_DELIMITER=,
CSV_ENCODING=utf-8

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=csv_documents

# Embedding Configuration
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_BATCH_SIZE=32

# Processing Configuration
MAX_CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Logging
LOG_LEVEL=INFO
```

## Troubleshooting

### Port Already in Use

If port 8000 is busy:
```bash
# Use a different port
uvicorn app.web_api:app --host 0.0.0.0 --port 8080
```

### Qdrant Connection Failed

Check if Qdrant is running:
```bash
docker ps | grep qdrant
curl http://localhost:6333/health
```

Restart Qdrant:
```bash
docker-compose restart qdrant
```

### Upload Fails

Check directory permissions:
```bash
mkdir -p data/uploads
chmod 755 data/uploads
```

### No Query Results

1. Verify CSV was uploaded successfully
2. Check Qdrant has vectors:
   ```bash
   curl http://localhost:6333/collections/csv_documents
   ```
3. Try a broader query or lower score threshold

## Sample CSV Files

Create a test CSV file:

```csv
title,description,category
Product A,High quality widget for home use,Electronics
Product B,Professional grade tool,Tools
Product C,Eco-friendly cleaning solution,Home & Garden
```

Save as `test_data.csv` and upload through the UI.

## API Endpoints

The web UI uses these REST endpoints:

- `POST /api/upload-csv` - Upload CSV file
- `POST /api/query` - Query documents
- `GET /api/health` - Check system health
- `GET /api/uploaded-files` - List uploaded files

See `app/frontend/README.md` for detailed API documentation.

## Next Steps

1. **Upload your CSV files** - Start with small files to test
2. **Experiment with queries** - Try different natural language questions
3. **Adjust parameters** - Tune chunk size, overlap, and score thresholds
4. **Monitor performance** - Check health status and processing times

## Advanced Usage

### Custom Embedding Models

Edit `.env`:
```bash
EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### Larger Chunks

For longer context:
```bash
MAX_CHUNK_SIZE=2000
CHUNK_OVERLAP=400
```

### Production Deployment

1. Use environment variables for secrets
2. Enable HTTPS with reverse proxy (nginx/traefik)
3. Add authentication middleware
4. Configure CORS for your domain
5. Set up monitoring and logging
6. Use persistent volumes for data

## Support

- Check logs: `docker-compose logs -f web-ui`
- View browser console for frontend errors
- Check `data/uploads/` for uploaded files
- Verify Qdrant collections: http://localhost:6333/dashboard

## Files Created

```
app/
├── frontend/
│   ├── index.html      # Main UI
│   ├── app.js          # Frontend logic
│   ├── styles.css      # Styling
│   └── README.md       # Frontend docs
├── web_api.py          # FastAPI endpoints
└── web_server.py       # Server runner

data/
└── uploads/            # Uploaded CSV files
```

Enjoy using the RAG MCP Server Web UI! 🚀
