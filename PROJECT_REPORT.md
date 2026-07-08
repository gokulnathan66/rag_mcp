# RAG MCP Server - Comprehensive Project Report

**Project Name:** Retrieval-Augmented Generation (RAG) MCP Server
**Version:** 1.0.0
**Current Branch:** feature/http_mcp
**Last Updated:** 2025-10-24

---

## Executive Summary

The RAG MCP Server is a production-ready Retrieval-Augmented Generation system that implements the Model Context Protocol (MCP) using FastMCP framework. It provides semantic document retrieval capabilities through vector embeddings and similarity search, enabling AI models and applications to query and analyze documents effectively.

**Key Capabilities:**
- Document ingestion from CSV files
- Vector embedding generation using FastEmbed
- Semantic similarity search via Qdrant vector database
- Dual transport support: HTTP and stdio
- Real-time Firestore document synchronization
- Comprehensive health monitoring and logging
- Production-ready containerization

---

## 1. Project Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│              MCP Clients (HTTP/stdio)                   │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌──────▼──────┐
    │  HTTP    │          │   Stdio     │
    │Transport │          │  Transport  │
    └────┬─────┘          └──────┬──────┘
         │                       │
         └───────────┬───────────┘
                     │
        ┌────────────▼────────────┐
        │    FastMCP Server       │
        │  (main.py)             │
        └────────────┬────────────┘
                     │
        ┌────────────▼─────────────────────┐
        │    MCP Tools & Business Logic    │
        ├─────────────────────────────────┤
        │ • ingest_csv()                  │
        │ • query_documents()             │
        │ • get_server_status()           │
        │ • get_http_health()             │
        └────────────┬─────────────────────┘
                     │
        ┌────────────▼──────────────────┐
        │    Orchestrator (LangGraph)   │
        │  (orchestrator.py)            │
        ├──────────────────────────────┤
        │ Workflow Coordination:        │
        │ • CSV Parsing Pipeline        │
        │ • Document Chunking           │
        │ • Embedding Generation        │
        │ • Vector Indexing             │
        │ • Similarity Search           │
        └────┬──────┬──────┬────────────┘
             │      │      │
        ┌────▼──┐ ┌──▼────┐ │
        │ CSV   │ │FastEmbed  │
        │Parser │ │(Embedder) │
        └────┬──┘ └──┬─────┘  │
             │       │         │
        ┌────▼───────▼─────────▼──┐
        │  Qdrant Vector Database  │
        │  (Vector Storage &       │
        │   Similarity Search)     │
        └──────────────────────────┘
             │
        ┌────▼─────────────────────┐
        │   Firestore (Optional)   │
        │  Document Synchronization│
        └──────────────────────────┘
```

### 1.2 Component Breakdown

#### FastMCP Server (`app/main.py`)
- **Role:** MCP protocol handler and orchestrator
- **Responsibilities:**
  - Server initialization and lifecycle management
  - Tool registration and invocation
  - Signal handling for graceful shutdown
  - Component initialization coordination
  - Error handling and logging

#### Orchestrator (`app/orchestrator.py`)
- **Role:** Workflow coordination engine
- **Responsibilities:**
  - LangGraph workflow management
  - CSV ingestion pipeline
  - Document chunking
  - Embedding generation coordination
  - Vector database operations
  - Health checking

#### Embedder (`app/embedder.py`)
- **Role:** Vector embedding generation
- **Model:** sentence-transformers/all-MiniLM-L6-v2
- **Responsibilities:**
  - Text-to-vector conversion
  - Batch processing support
  - Model loading and caching
  - Dimension: 384 (default)

#### Qdrant Client (`app/qdrant_client.py`)
- **Role:** Vector database operations
- **Responsibilities:**
  - Collection management
  - Vector storage
  - Similarity search
  - Payload metadata handling
  - Connection pooling

#### Configuration (`app/config.py`)
- **Role:** Settings management
- **Features:**
  - Environment variable support
  - Pydantic validation
  - HTTP transport configuration
  - CSV processing settings
  - Firestore credentials

#### HTTP Components (HTTP Transport)
- **HTTP Monitoring:** Connection tracking and metrics
- **HTTP Connection Manager:** Connection lifecycle management
- **HTTP Health Checker:** Health endpoint integration

---

## 2. Technology Stack

### Core Technologies

| Technology | Version | Purpose |
|-----------|---------|---------|
| **FastMCP** | >=0.1.0 | MCP protocol implementation |
| **FastAPI** | >=0.104.0 | HTTP framework |
| **Uvicorn** | >=0.24.0 | ASGI server |
| **Pydantic** | >=2.0.0 | Data validation |
| **Qdrant** | >=1.7.0 | Vector database |
| **FastEmbed** | >=0.2.0 | Vector embeddings |
| **LangGraph** | >=0.1.0 | Workflow orchestration |
| **Logfire** | >=0.1.0 | Monitoring & logging |

### Environment & Deployment

| Component | Purpose |
|-----------|---------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration |
| **Kubernetes** | Production deployment (optional) |
| **Python 3.13** | Runtime environment |

---

## 3. How the System Works

### 3.1 Document Ingestion Flow

```
CSV File Input
    ↓
CSV Parser (app/models.py)
    ↓ Parse rows into documents
Document Objects
    ↓
Chunker (app/orchestrator.py)
    ↓ Split into chunks (default: 1000 chars, overlap: 200)
Chunks
    ↓
FastEmbed Embedder
    ↓ Generate 384-dim vectors
Embeddings (vectors + metadata)
    ↓
Qdrant Storage
    ↓ Store in collection
Indexing Complete
    ↓
Status returned to client
```

**Steps:**
1. **File Validation:** Verify CSV file exists and is accessible
2. **CSV Parsing:** Read CSV with configurable delimiter and encoding
3. **Document Creation:** Extract rows as documents with metadata
4. **Chunking:** Split large documents using configurable chunk size
5. **Embedding:** Generate vectors using FastEmbed model
6. **Storage:** Persist vectors in Qdrant with metadata
7. **Response:** Return ingestion status with metrics

### 3.2 Query/Search Flow

```
Natural Language Query
    ↓
Query Validation
    ↓
FastEmbed Embedding
    ↓ Convert query to 384-dim vector
Query Vector
    ↓
Qdrant Similarity Search
    ↓ Find k similar vectors
Similarity Scores
    ↓
Threshold Filtering (optional)
    ↓
Result Ranking
    ↓
Return Top-K Results
    ↓
Client Response
```

**Steps:**
1. **Query Reception:** Accept natural language query
2. **Vector Generation:** Convert query to embedding
3. **Database Search:** Perform cosine similarity search
4. **Filtering:** Apply optional score threshold
5. **Ranking:** Sort by similarity score
6. **Metadata Retrieval:** Include document metadata
7. **Response Formation:** Return ranked results with scores

### 3.3 HTTP Transport Flow

```
HTTP Client
    ↓
HTTP Request (JSON-RPC 2.0)
    ↓
HTTPConnectionManager
    ↓ Track connection
Route Handler
    ↓
FastMCP Tool Invocation
    ↓
Business Logic Execution
    ↓
Response Generation
    ↓
HTTPMonitor
    ↓ Record metrics
HTTP Response (JSON)
    ↓
HTTP Client
```

---

## 4. MCP Tools & API

### 4.1 Available Tools

#### 1. `ingest_csv`
**Purpose:** Ingest documents from CSV files into the vector database

**Input Parameters:**
```python
{
    "file_path": "str"  # Path to CSV file (e.g., "data/sample.csv")
}
```

**Output (IngestionStatus):**
```python
{
    "status": "success" | "failed",
    "collection_name": "str",
    "documents_processed": int,
    "chunks_created": int,
    "embeddings_generated": int,
    "errors": List[str],
    "processing_time_seconds": float
}
```

**Example Usage:**
```bash
# Via HTTP
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "ingest_csv",
    "params": {"input_data": {"file_path": "data/sample_data.csv"}},
    "id": 1
  }'
```

**Key Features:**
- Automatic chunk creation
- Concurrent embedding generation
- Error resilience with partial ingestion
- Comprehensive metrics reporting

---

#### 2. `query_documents`
**Purpose:** Search documents using natural language similarity

**Input Parameters:**
```python
{
    "query": "str",                    # Search query
    "max_results": int = 10,          # Number of results (1-100)
    "score_threshold": Optional[float] # Minimum similarity (0.0-1.0)
}
```

**Output (List[QueryResult]):**
```python
[
    {
        "document_id": "str",
        "chunk_id": "str",
        "content": "str",
        "similarity_score": float,
        "metadata": {
            "document_id": "str",
            "chunk_id": "str",
            "content": "str",
            "chunk_index": int,
            "embedding_model": "str",
            "source_file": "str",
            "row_number": int,
            "ingestion_time": "str",
            "document_type": "str",
            "chunking_strategy": "str"
        },
        "csv_metadata": {
            "document_id": "str",
            "source_file": "str",
            "row_number": int,
            "content": dict,
            "ingestion_time": "str"
        }
    },
    ...
]
```

**Example Usage:**
```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "query_documents",
    "params": {
      "input_data": {
        "query": "lunch with kanishk",
        "max_results": 5,
        "score_threshold": 0.3
      }
    },
    "id": 2
  }'
```

**Key Features:**
- Semantic similarity matching
- Configurable result limits
- Optional score filtering
- Rich metadata in results

---

#### 3. `get_server_status`
**Purpose:** Check server and component health

**Input Parameters:** None

**Output (ServerStatus):**
```python
{
    "server_name": "str",
    "version": "str",
    "status": "running" | "error",
    "uptime_seconds": float,
    "components": {
        "csv_parser": "ok" | "error" | "unknown",
        "fastembed": "ok" | "error" | "unknown",
        "qdrant_client": "ok" | "error" | "unknown",
        "langgraph": "ok" | "error" | "unknown"
    },
    "last_health_check": "str"  # ISO timestamp
}
```

**Example Usage:**
```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "get_server_status",
    "params": {},
    "id": 3
  }'
```

---

#### 4. `get_http_health` (HTTP Transport Only)
**Purpose:** Get detailed HTTP transport health and metrics

**Input Parameters:** None

**Output:**
```python
{
    "status": "healthy" | "degraded" | "unhealthy",
    "timestamp": "str",  # ISO timestamp
    "server_name": "str",
    "version": "str",
    "uptime_seconds": float,
    "components": dict,
    "http_transport": {
        "transport_mode": "http",
        "host": "str",
        "port": int,
        "max_connections": int,
        "connection_timeout": int,
        "cors_enabled": bool,
        "health_endpoint_enabled": bool,
        "connection_stats": {
            "active_connections": int,
            "total_connections": int,
            "connection_utilization": float
        },
        "http_metrics": {
            "total_requests": int,
            "successful_requests": int,
            "failed_requests": int,
            "avg_response_time": float,
            "error_rate": float,
            "last_updated": "str"
        }
    }
}
```

---

### 4.2 Error Handling

All tools follow a consistent error handling pattern:

**Error Response Structure:**
```json
{
    "jsonrpc": "2.0",
    "error": {
        "code": -32603,
        "message": "Error description",
        "data": {
            "error_code": "ERROR_TYPE",
            "error_message": "Detailed message",
            "correlation_id": "uuid"
        }
    },
    "id": 1
}
```

**Common Error Codes:**
- `CSV_PARSE_ERROR`: CSV file parsing failed
- `EMBEDDING_ERROR`: Vector embedding generation failed
- `QDRANT_ERROR`: Database operation failed
- `VALIDATION_ERROR`: Input validation failed
- `NOT_FOUND`: Resource not found
- `SERVER_ERROR`: Unexpected server error

---

## 5. Transport Mechanisms

### 5.1 HTTP Transport (Primary)

**Configuration:**
```env
TRANSPORT_MODE=http
HTTP_HOST=0.0.0.0
HTTP_PORT=8080
MAX_CONCURRENT_CONNECTIONS=100
CONNECTION_TIMEOUT=300
ENABLE_CORS=true
ENABLE_HEALTH_ENDPOINT=true
HEALTH_CHECK_PATH=/health
```

**Endpoints:**
- **MCP Endpoint:** `http://{host}:{port}/mcp/`
- **Health Endpoint:** `http://{host}:{port}/health`

**Features:**
- JSON-RPC 2.0 over HTTP
- CORS support for web clients
- Connection pooling and management
- Health check endpoint for load balancers
- Request/connection timeout handling

**Health Endpoint Response:**
```json
{
    "status": "healthy",
    "timestamp": "2025-10-24T04:41:23.522615Z",
    "server_name": "csv-rag-server",
    "version": "1.0.0",
    "uptime_seconds": 66475.69,
    "components": {
        "csv_parser": "ok",
        "fastembed": "ok",
        "qdrant_client": "ok",
        "langgraph": "ok"
    }
}
```

### 5.2 Stdio Transport (Default)

**Configuration:**
```env
TRANSPORT_MODE=default
```

**Features:**
- Direct stdin/stdout communication
- No network overhead
- Suitable for local process communication
- CLI tool integration

---

## 6. Configuration Management

### 6.1 Configuration Sources

Priority (highest to lowest):
1. **Environment Variables**
2. **System Environment** (fallback)
3. **Default Values**

### 6.2 Environment Variables

**Transport Configuration:**
```env
TRANSPORT_MODE=http              # 'default' or 'http'
HTTP_HOST=0.0.0.0               # HTTP server host
HTTP_PORT=8080                   # HTTP server port (1024-65535)
MAX_CONCURRENT_CONNECTIONS=100   # Connection limit
CONNECTION_TIMEOUT=300           # Connection timeout (seconds)
REQUEST_TIMEOUT=60               # Request timeout (seconds)
ENABLE_CORS=true                 # CORS support
ENABLE_HEALTH_ENDPOINT=true      # Health check endpoint
HEALTH_CHECK_PATH=/health        # Health endpoint path
```

**CSV Configuration:**
```env
CSV_DATA_DIRECTORY=./data        # CSV file directory
CSV_DELIMITER=,                  # CSV delimiter
CSV_ENCODING=utf-8               # Character encoding
```

**Qdrant Configuration:**
```env
QDRANT_URL=http://localhost:6333 # Qdrant server URL
QDRANT_API_KEY=                  # Optional API key
QDRANT_COLLECTION_NAME=firestore_documents  # Collection name
```

**FastEmbed Configuration:**
```env
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_BATCH_SIZE=32          # Batch size for embeddings
ENABLE_SPARSE_EMBEDDINGS=false   # Hybrid search support
```

**Processing Configuration:**
```env
MAX_CHUNK_SIZE=1000              # Document chunk size
CHUNK_OVERLAP=200                # Chunk overlap
MAX_CONCURRENT_REQUESTS=10       # Concurrent request limit
```

**Monitoring Configuration:**
```env
ENABLE_LOGFIRE=true              # Logfire monitoring
LOG_LEVEL=INFO                   # Logging level
```

**Firestore Configuration (Optional):**
```env
FIRESTORE_PROJECT_ID=your-project-id
FIRESTORE_CREDENTIALS_PATH=/path/to/credentials.json
FIRESTORE_DATABASE_ID=(default)
```

### 6.3 Configuration Priority Example

```python
# Example: HTTP_PORT resolution
1. Check environment variable: $HTTP_PORT
   └─ If set, use this value
2. Check system environment
   └─ If set, use this value
3. Use default
   └─ Use 8080 (defined in config.py)
```

---

## 7. Project Structure

```
rag_mcp/
├── app/
│   ├── __init__.py
│   ├── main.py                      # Server entry point (1314 lines)
│   ├── config.py                    # Configuration management
│   ├── models.py                    # Data models & schemas
│   ├── orchestrator.py              # LangGraph workflow
│   ├── embedder.py                  # FastEmbed wrapper
│   ├── qdrant_client.py             # Qdrant operations
│   ├── firestore_sync.py            # Firestore integration (optional)
│   ├── http_monitoring.py           # HTTP metrics tracking
│   ├── http_connection_manager.py   # Connection lifecycle
│   ├── http_health_check.py         # Health checking
│   ├── errors.py                    # Error handling
│   └── utils.py                     # Helper functions
├── tests/
│   ├── test_*.py                    # Test suite
│   └── conftest.py                  # Pytest fixtures
├── data/
│   ├── sample_data.csv              # Sample CSV
│   ├── sample_products.csv          # Sample products
│   └── uploads/                     # User uploads
├── qdrant_storage/                  # Vector DB persistence
├── .dockerignore                    # Docker ignore patterns
├── .gitignore                       # Git ignore patterns
├── Dockerfile                       # Container image
├── docker-compose.yml               # Multi-container setup
├── requirements.txt                 # Python dependencies
├── CLAUDE.md                        # Project knowledge base
├── README.md                        # Project documentation
└── k8s-deployment.yml               # Kubernetes manifest

```

---

## 8. Deployment Options

### 8.1 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with stdio transport
python app/main.py

# Or with HTTP transport
export TRANSPORT_MODE=http
python app/main.py
```

### 8.2 Docker Deployment

```bash
# Build image
docker build -t rag-mcp:1.0.0 .

# Run container
docker run -d \
  -e TRANSPORT_MODE=http \
  -e HTTP_PORT=8080 \
  -e QDRANT_URL=http://qdrant:6333 \
  -p 8080:8080 \
  rag-mcp:1.0.0
```

### 8.3 Docker Compose

```bash
# Start services
docker-compose up -d

# Check logs
docker-compose logs -f rag_mcp

# Stop services
docker-compose down
```

### 8.4 Kubernetes Deployment

```bash
# Deploy to K8s cluster
kubectl apply -f k8s-deployment.yml

# Check status
kubectl get pods -l app=rag-mcp

# View logs
kubectl logs -f deployment/rag-mcp
```

---

## 9. Lifecycle Management

### 9.1 Server Startup Sequence

```
1. Signal Handlers Setup
   ├─ SIGTERM handler (graceful shutdown)
   └─ SIGINT handler (Ctrl+C)

2. Configuration Loading
   ├─ Environment variables
   ├─ Default values
   └─ Validation

3. Component Initialization (Parallel)
   ├─ CSV Parser
   ├─ FastEmbed Embedder
   ├─ Qdrant Client
   │  └─ Connection & collection setup
   └─ Health Check

4. HTTP Transport Setup (if enabled)
   ├─ HTTP Monitor
   ├─ Connection Manager
   └─ Health Endpoint

5. FastMCP Server Creation
   ├─ Tool Registration
   │  ├─ ingest_csv
   │  ├─ query_documents
   │  ├─ get_server_status
   │  └─ get_http_health (HTTP only)
   └─ Logfire Configuration

6. Server Start
   ├─ Bind to host:port (HTTP) or stdio (default)
   └─ Accept connections
```

### 9.2 Graceful Shutdown

**Trigger Events:**
- SIGTERM signal (container termination)
- SIGINT signal (Ctrl+C)
- SystemExit
- Keyboard interrupt

**Shutdown Sequence:**
```
1. Signal Reception
   └─ Set shutdown flag

2. HTTP Transport Shutdown (if enabled)
   ├─ Close connections gracefully
   ├─ Drain in-flight requests (10s timeout)
   └─ Shutdown HTTP monitor

3. Orchestrator Shutdown
   ├─ Close Qdrant connection
   ├─ Stop LangGraph workflows
   ├─ Cleanup thread pools
   └─ Release resources (15s timeout)

4. State Cleanup
   └─ Clear global instances

5. Logfire Flush
   └─ Send remaining logs

6. Process Exit
   └─ Clean exit code (0 for success, 1 for error)
```

**Timeout Configuration:**
- Total shutdown timeout: 30s (container-friendly)
- HTTP shutdown: 10s
- Orchestrator shutdown: 15s
- Buffer: 5s (before container force-kill)

---

## 10. Monitoring & Observability

### 10.1 Logfire Integration

**Enabled Spans:**
- `ingest_csv` - Document ingestion
- `query_documents` - Document search
- `get_server_status` - Health check
- `get_http_health` - HTTP health check
- `http_server_startup` - Server initialization
- `mcp_server_startup` - Server startup

**Span Context Includes:**
- Correlation ID (UUID)
- Transport mode
- Operation parameters
- Timestamps
- HTTP endpoint info (when applicable)

### 10.2 Health Check Endpoints

**MCP Tool:** `get_server_status`
```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "get_server_status", "id": 1}'
```

**HTTP Endpoint:** `GET /health`
```bash
curl http://localhost:8080/health
```

**Status Indicators:**
- Component health (ok/error/unknown)
- Server uptime
- Connection statistics
- Request metrics
- Error rates

### 10.3 Metrics Tracking

**Connection Metrics:**
- Active connections
- Total connections
- Connection utilization (%)

**Request Metrics:**
- Total requests
- Successful requests
- Failed requests
- Average response time
- Error rate (%)

---

## 11. Error Handling

### 11.1 Error Categories

**CSV Processing Errors:**
- File not found
- Parsing errors
- Encoding issues
- Invalid format

**Embedding Errors:**
- Model loading failure
- Vector generation failure
- Batch processing failure

**Database Errors:**
- Connection failure
- Collection not found
- Query failure
- Storage failure

**Validation Errors:**
- Invalid input parameters
- Type mismatches
- Out-of-range values

**System Errors:**
- Out of memory
- File system errors
- Port binding errors
- Network errors

### 11.2 Error Response Example

```json
{
    "jsonrpc": "2.0",
    "error": {
        "code": -32603,
        "message": "CSV parsing error",
        "data": {
            "error_code": "CSV_PARSE_ERROR",
            "error_message": "CSV file not found: data/sample.csv",
            "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        }
    },
    "id": 1
}
```

### 11.3 Error Logging

All errors logged with:
- Timestamp
- Correlation ID
- Component name
- Error code and message
- Stack trace (debug mode)
- Context information

---

## 12. Performance Considerations

### 12.1 Optimization Strategies

**Embedding Generation:**
- Batch processing (configurable batch size)
- ONNX runtime acceleration
- Cached model instances
- Async operations

**Vector Search:**
- Qdrant indexing
- Configurable search limits
- Score thresholding
- Result pagination

**Connection Management:**
- Connection pooling
- Async I/O
- Concurrent request handling
- Timeout management

### 12.2 Scaling Recommendations

| Metric | Recommended | Max |
|--------|-------------|-----|
| Concurrent connections | 50-100 | 1000 |
| Max chunk size | 1000 chars | 10000 |
| Batch size | 32 | 256 |
| Request timeout | 60s | 300s |
| Collection size | 100K vectors | 10M+ |

---

## 13. Security Considerations

### 13.1 Security Features

**Input Validation:**
- Pydantic schema validation
- Type checking
- Range validation
- Path traversal protection

**Transport Security:**
- CORS configuration
- Connection timeout
- Max request size
- Rate limiting ready

**Secrets Management:**
- Environment variable support
- No hardcoded credentials
- Optional API key support

### 13.2 Security Best Practices

1. **Use HTTPS in production** (behind reverse proxy)
2. **Implement authentication** (add middleware)
3. **Configure CORS appropriately** (restrict origins)
4. **Use API keys** for Qdrant
5. **Validate all inputs** (already implemented)
6. **Monitor access logs** (via Logfire)
7. **Keep dependencies updated**
8. **Use environment variables** for secrets

---

## 14. Development & Testing

### 14.1 Test Suite

Located in `tests/` directory:
- Unit tests for components
- Integration tests
- API tests
- Performance tests

**Running Tests:**
```bash
pytest tests/ -v
pytest tests/ --asyncio-mode=auto
pytest tests/ -k "ingest" -v
```

### 14.2 Development Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes to code
3. Run tests: `pytest tests/ -v`
4. Commit: `git commit -m "your message"`
5. Push: `git push origin feature/your-feature`
6. Create Pull Request

---

## 15. Known Issues & Fixes

### 15.1 Recent Fixes (Git History)

| Commit | Issue | Fix |
|--------|-------|-----|
| ab6b18c | Time handling error | Fixed datetime operations |
| d1bdba0 | Port conflict | Changed from 8000 to 8080 |
| beffd4d | HTTP streaming | Initial implementation |
| 43b98e1 | CSV parsing | Edge case handling |

### 15.2 Current Limitations

1. **Single Qdrant Instance:** No clustering support
2. **No Authentication:** Add middleware for auth
3. **No Rate Limiting:** Implement if needed
4. **No Request Caching:** Could improve performance
5. **No Multi-tenancy:** Single tenant only

---

## 16. Future Enhancements

### 16.1 Roadmap

- **v1.1:** Hybrid search (dense + sparse)
- **v1.2:** Advanced filtering options
- **v1.3:** Request caching layer
- **v1.4:** Multi-tenant support
- **v2.0:** Real-time streaming responses

### 16.2 Potential Improvements

1. **Caching:** Redis layer for frequent queries
2. **Authentication:** OAuth2 or API key system
3. **Rate Limiting:** Per-user or per-IP limits
4. **Advanced Search:** Full-text + semantic
5. **Analytics:** Query analytics and insights
6. **Custom Models:** Support for fine-tuned embeddings

---

## 17. Troubleshooting Guide

### Issue: Port Already in Use

**Error:** "Address already in use"
**Solution:**
```bash
# Find process using port 8080
lsof -i :8080
# Kill process
kill -9 <PID>
# Or change port
export HTTP_PORT=8081
```

### Issue: Qdrant Connection Failed

**Error:** "Cannot connect to Qdrant"
**Solution:**
```bash
# Check Qdrant is running
docker ps | grep qdrant
# Start Qdrant
docker-compose up -d qdrant
# Check URL
export QDRANT_URL=http://qdrant:6333
```

### Issue: Out of Memory

**Error:** Memory allocation failure
**Solution:**
- Increase container memory: `docker run -m 2g`
- Reduce batch size: `EMBEDDING_BATCH_SIZE=16`
- Reduce max connections: `MAX_CONCURRENT_CONNECTIONS=50`

### Issue: CSV File Not Found

**Error:** "CSV file not found"
**Solution:**
```bash
# Verify file exists
ls -la data/sample_data.csv
# Use correct path
# Relative: data/sample_data.csv (from working directory)
# Absolute: /full/path/to/file.csv
```

---

## 18. Integration Examples

### 18.1 Python Client

```python
import httpx
import asyncio

async def query_documents():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/mcp/",
            json={
                "jsonrpc": "2.0",
                "method": "query_documents",
                "params": {
                    "input_data": {
                        "query": "lunch with kanishk",
                        "max_results": 5
                    }
                },
                "id": 1
            }
        )
        print(response.json())

asyncio.run(query_documents())
```

### 18.2 JavaScript/Node.js Client

```javascript
async function queryDocuments() {
    const response = await fetch('http://localhost:8080/mcp/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'query_documents',
            params: {
                input_data: {
                    query: 'lunch with kanishk',
                    max_results: 5
                }
            },
            id: 1
        })
    });
    const data = await response.json();
    console.log(data);
}

queryDocuments();
```

---

## 19. Conclusion

The RAG MCP Server is a comprehensive, production-ready system for semantic document retrieval. Its modular architecture, robust error handling, and flexible deployment options make it suitable for various use cases ranging from local development to large-scale production deployments.

**Key Strengths:**
- Modern Python async architecture
- Flexible transport mechanisms
- Comprehensive monitoring
- Container-friendly design
- Extensible component system

**Best Use Cases:**
- AI model integration
- Document search applications
- Knowledge base systems
- Semantic search engines
- Content retrieval platforms

---

## 20. Quick Reference

**Start HTTP Server:**
```bash
export TRANSPORT_MODE=http
python app/main.py
```

**Start with Docker:**
```bash
docker-compose up -d
```

**Query Health:**
```bash
curl http://localhost:8080/health
```

**Ingest CSV:**
```bash
curl -X POST http://localhost:8080/mcp/ -d '{
  "jsonrpc": "2.0",
  "method": "ingest_csv",
  "params": {"input_data": {"file_path": "data/sample.csv"}},
  "id": 1
}'
```

**Search Documents:**
```bash
curl -X POST http://localhost:8080/mcp/ -d '{
  "jsonrpc": "2.0",
  "method": "query_documents",
  "params": {"input_data": {"query": "your search query", "max_results": 10}},
  "id": 2
}'
```

---

**Document Generated:** 2025-10-24
**Version:** 1.0.0
**Status:** Production Ready
