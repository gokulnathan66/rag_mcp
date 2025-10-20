# RAG MCP Server - Complete System Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                              │
├─────────────────────────────────┬───────────────────────────────────┤
│         Web Browser             │      MCP Client (Kiro/Claude)     │
│  ┌──────────────────────────┐   │   ┌──────────────────────────┐   │
│  │   Upload CSV Files       │   │   │   Tool: ingest_csv       │   │
│  │   Query Documents        │   │   │   Tool: query_documents  │   │
│  │   View Results           │   │   │   Tool: get_server_status│   │
│  └────────────┬─────────────┘   │   └────────────┬─────────────┘   │
└───────────────┼─────────────────┴────────────────┼─────────────────┘
                │                                   │
                │ HTTP/REST                         │ JSON-RPC (stdio)
                │                                   │
┌───────────────▼─────────────────┬────────────────▼─────────────────┐
│      FastAPI Web Server         │      FastMCP Server              │
│      (app/web_server.py)        │      (app/main.py)               │
│  Port: 8000                     │  Protocol: stdio                 │
└───────────────┬─────────────────┴────────────────┬─────────────────┘
                │                                   │
                └──────────────┬────────────────────┘
                               │
                               │ Direct Python calls
                               │
                ┌──────────────▼──────────────┐
                │    LangGraph Orchestrator    │
                │    (app/orchestrator.py)     │
                │                              │
                │  ┌────────────────────────┐  │
                │  │  Ingestion Workflow    │  │
                │  │  Parse → Chunk →       │  │
                │  │  Embed → Store         │  │
                │  └────────────────────────┘  │
                │                              │
                │  ┌────────────────────────┐  │
                │  │  Query Workflow        │  │
                │  │  Embed → Search →      │  │
                │  │  Format Results        │  │
                │  └────────────────────────┘  │
                └──────────────┬──────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌──────────────────┐    ┌──────────────┐
│  CSV Parser   │    │    FastEmbed     │    │   Qdrant     │
│               │    │  (ONNX Runtime)  │    │   Client     │
└───────┬───────┘    └────────┬─────────┘    └──────┬───────┘
        │                     │                      │
        ▼                     ▼                      ▼
┌───────────────┐    ┌──────────────────┐    ┌──────────────┐
│  CSV Files    │    │  Embedding       │    │   Qdrant     │
│  data/        │    │  Models          │    │   Database   │
│  uploads/     │    │  (cached)        │    │   (Docker)   │
└───────────────┘    └──────────────────┘    └──────────────┘
```

## Two Ways to Use the System

### 1. Web UI (Human Users)

**Purpose**: Interactive document management and querying

**How to Start**:
```bash
./start_web_ui.sh
# or
python -m app.web_server
```

**Access**: http://localhost:8000

**Features**:
- Upload CSV files via browser
- Query with natural language
- View results with scores
- Monitor system health

**Use Cases**:
- Manual document ingestion
- Ad-hoc queries
- Testing and exploration
- Demonstrations

### 2. MCP Server (AI Assistants)

**Purpose**: Tool integration for AI assistants (Kiro, Claude, etc.)

**How to Start**:
```bash
python -m app.main
```

**Protocol**: JSON-RPC over stdio

**Features**:
- `ingest_csv(file_path)` - Ingest CSV files
- `query_documents(query, max_results)` - Query documents
- `get_server_status()` - Check health

**Use Cases**:
- Automated workflows
- AI assistant integration
- Programmatic access
- Batch processing

## Data Flow Comparison

### Web UI Upload Flow

```
1. User selects CSV in browser
   ↓
2. JavaScript FormData POST to /api/upload-csv
   ↓
3. FastAPI saves file to data/uploads/filename.csv
   ↓
4. FastAPI calls orchestrator.ingest_csv("/path/to/file.csv")
   ↓
5. Orchestrator runs LangGraph workflow
   ↓
6. Returns IngestionStatus to FastAPI
   ↓
7. FastAPI returns JSON response to browser
   ↓
8. JavaScript displays results
```

### MCP Server Ingestion Flow

```
1. MCP Client calls ingest_csv tool
   ↓
2. FastMCP receives JSON-RPC request
   ↓
3. FastMCP calls orchestrator.ingest_csv("/path/to/file.csv")
   ↓
4. Orchestrator runs LangGraph workflow
   ↓
5. Returns IngestionStatus to FastMCP
   ↓
6. FastMCP returns JSON-RPC response
   ↓
7. MCP Client receives result
```

**Key Difference**: Web UI accepts file uploads, MCP Server expects file paths

## Query Flow (Same for Both)

```
1. User/Client submits query
   ↓
2. Server receives query text
   ↓
3. Orchestrator.query() called
   ↓
4. LangGraph Query Workflow:
   a. FastEmbed converts query to vector
   b. Qdrant searches for similar vectors
   c. Results assembled with metadata
   ↓
5. Returns List[QueryResult]
   ↓
6. Response formatted and returned
```

## Component Responsibilities

### CSV Parser (app/csv_parser.py)
- Reads CSV files from filesystem
- Handles various encodings (UTF-8, Latin-1, etc.)
- Parses rows into structured documents
- Generates unique document IDs
- Preserves metadata (row numbers, source file)

### Embedder (app/embedder.py)
- Chunks large documents into segments
- Generates vector embeddings using FastEmbed
- Uses ONNX-optimized models for speed
- Batch processing for efficiency
- Default model: sentence-transformers/all-MiniLM-L6-v2

### Qdrant Client (app/qdrant_client.py)
- Manages vector database connections
- Creates and configures collections
- Stores vectors with metadata
- Performs similarity searches
- Handles batch operations

### Orchestrator (app/orchestrator.py)
- Coordinates multi-step workflows using LangGraph
- Manages state between processing steps
- Handles errors and retries
- Provides high-level API for both servers

## Storage Layers

### 1. CSV Files (Source Documents)
```
data/
├── uploads/           # Web UI uploaded files
│   ├── products.csv
│   └── customers.csv
└── sample_products.csv # Sample data
```

### 2. Qdrant Vector Database
```
Qdrant (Docker Container)
├── Collection: csv_documents
│   ├── Vectors (384-dimensional)
│   └── Payloads (metadata)
└── Storage: ./qdrant_storage/
```

### 3. Embedding Models (Cached)
```
~/.cache/fastembed/
└── sentence-transformers/
    └── all-MiniLM-L6-v2/
```

## Configuration

Both servers use the same configuration from `.env`:

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

# Monitoring
LOG_LEVEL=INFO
ENABLE_LOGFIRE=true
```

## Deployment Options

### Development (Local)

**Option 1: Standalone**
```bash
# Start Qdrant
docker-compose up -d qdrant

# Start Web UI
python -m app.web_server

# Or start MCP Server
python -m app.main
```

**Option 2: Docker Compose**
```bash
# Start everything
docker-compose up -d

# Web UI: http://localhost:8001
# Qdrant Dashboard: http://localhost:6333/dashboard
```

### Production

**Recommended Stack**:
- **Web Server**: Kubernetes/ECS with multiple replicas
- **Qdrant**: Managed Qdrant Cloud or self-hosted cluster
- **Load Balancer**: nginx/traefik with SSL
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK stack or CloudWatch

## Performance Characteristics

### Ingestion
- **Speed**: ~100-500 rows/second (depends on content size)
- **Bottleneck**: Embedding generation
- **Optimization**: Batch processing, async operations

### Query
- **Latency**: 50-200ms typical
- **Bottleneck**: Qdrant search (scales with collection size)
- **Optimization**: Qdrant indexing, score thresholds

### Scalability
- **Horizontal**: Multiple web server instances
- **Vertical**: More CPU for embedding generation
- **Database**: Qdrant clustering for large datasets

## Monitoring & Health

### Health Check Endpoints

**Web UI**:
```bash
curl http://localhost:8000/api/health
```

**MCP Server**:
```bash
# Call get_server_status tool
```

**Response**:
```json
{
  "status": "healthy",
  "components": {
    "csv_parser": "ok",
    "embedder": "ok",
    "qdrant": "ok"
  }
}
```

### Logs

**Web UI**:
```bash
# Stdout/stderr
python -m app.web_server

# Docker
docker-compose logs -f web-ui
```

**MCP Server**:
```bash
# Configured via LOG_LEVEL env var
# Outputs to stdout
```

## Security Considerations

### Current (Development)
- ❌ No authentication
- ❌ No rate limiting
- ❌ No file size limits
- ✅ Basic input validation

### Production Requirements
- ✅ JWT/OAuth authentication
- ✅ Rate limiting (per user/IP)
- ✅ File size/type validation
- ✅ HTTPS/TLS encryption
- ✅ CORS configuration
- ✅ Input sanitization
- ✅ Audit logging

## Common Workflows

### 1. Initial Setup
```bash
# Clone repository
git clone <repo>

# Install dependencies
pip install -r requirements.txt

# Start Qdrant
docker-compose up -d qdrant

# Start Web UI
./start_web_ui.sh
```

### 2. Upload and Query (Web UI)
```
1. Open http://localhost:8000
2. Upload CSV file
3. Wait for ingestion to complete
4. Enter query in search box
5. View results
```

### 3. Programmatic Access (MCP)
```python
# Configure MCP client
# Call ingest_csv tool with file path
# Call query_documents tool with query
# Process results
```

### 4. Batch Processing
```bash
# Upload multiple files
for file in data/*.csv; do
    curl -X POST http://localhost:8000/api/upload-csv \
         -F "file=@$file"
done
```

## Troubleshooting Guide

### Issue: Qdrant connection failed
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Check health
curl http://localhost:6333/health

# Restart
docker-compose restart qdrant
```

### Issue: Upload fails
```bash
# Check directory permissions
ls -la data/uploads/

# Create if missing
mkdir -p data/uploads
chmod 755 data/uploads
```

### Issue: No query results
```bash
# Check if vectors exist
curl http://localhost:6333/collections/csv_documents

# Verify ingestion succeeded
# Check logs for errors
```

### Issue: Slow performance
```bash
# Check Qdrant resource usage
docker stats qdrant

# Increase batch size in .env
EMBEDDING_BATCH_SIZE=64

# Use smaller chunks
MAX_CHUNK_SIZE=500
```

## Next Steps

1. **Try the sample data**: Upload `data/sample_products.csv`
2. **Test queries**: "wireless devices", "office equipment"
3. **Upload your data**: Prepare your CSV files
4. **Tune parameters**: Adjust chunk size and overlap
5. **Monitor performance**: Check health and logs
6. **Scale up**: Add authentication, deploy to production

## Resources

- **Quick Start**: [QUICKSTART_WEB_UI.md](QUICKSTART_WEB_UI.md)
- **Web UI Summary**: [WEB_UI_SUMMARY.md](WEB_UI_SUMMARY.md)
- **Architecture**: [app/frontend/ARCHITECTURE.md](app/frontend/ARCHITECTURE.md)
- **Requirements**: [.kiro/specs/rag-mcp-server/requirements.md](.kiro/specs/rag-mcp-server/requirements.md)
- **Design**: [.kiro/specs/rag-mcp-server/design.md](.kiro/specs/rag-mcp-server/design.md)

---

**You now have a complete RAG system with both web and MCP interfaces!** 🎉
