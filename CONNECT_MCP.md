# RAG MCP Server - Connection Guide

**How to Connect to and Use the RAG MCP Server**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Connection Methods](#connection-methods)
3. [Protocol Details](#protocol-details)
4. [Configuration](#configuration)
5. [Client Examples](#client-examples)
6. [Integration Patterns](#integration-patterns)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Quick Start

### Prerequisites

- Python 3.13+
- Docker (optional)
- 2GB+ RAM
- Network connectivity (for HTTP transport)

### Start the Server

**Option 1: Direct Python**
```bash
cd /Users/gokulnathanb/Projects/mine/rag_mcp

# Install dependencies (if not already done)
pip install -r requirements.txt

# Run with HTTP transport
export TRANSPORT_MODE=http
export HTTP_HOST=0.0.0.0
export HTTP_PORT=8080
python app/main.py
```

**Option 2: Docker Compose**
```bash
cd /Users/gokulnathanb/Projects/mine/rag_mcp

# Start all services (MCP server + Qdrant)
docker-compose up -d

# View logs
docker-compose logs -f rag_mcp
```

### Verify Connection

```bash
# Check health
curl http://localhost:8080/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-10-24T04:41:23.522615Z",
#   "server_name": "csv-rag-server",
#   "version": "1.0.0",
#   "uptime_seconds": 123.45,
#   "components": {
#     "csv_parser": "ok",
#     "fastembed": "ok",
#     "qdrant_client": "ok",
#     "langgraph": "ok"
#   }
# }
```

---

## Connection Methods

### 1. HTTP Transport (Recommended)

**Best for:** Network communication, web clients, remote connections

#### Setup

```bash
# Set environment variables
export TRANSPORT_MODE=http
export HTTP_HOST=0.0.0.0
export HTTP_PORT=8080
export ENABLE_CORS=true

# Start server
python app/main.py
```

#### Endpoints

- **MCP Endpoint:** `http://localhost:8080/mcp/`
- **Health Endpoint:** `http://localhost:8080/health`

#### Connection Info

```
Protocol: HTTP/1.1 with JSON-RPC 2.0
Host: localhost (or your server IP)
Port: 8080 (configurable)
Path: /mcp/
Content-Type: application/json
```

#### Curl Example

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "get_server_status",
    "params": {},
    "id": 1
  }'
```

### 2. Stdio Transport (Default)

**Best for:** Local process communication, CLI tools

#### Setup

```bash
# No environment variables needed (default is stdio)
python app/main.py < input.json > output.json
```

#### Connection Info

```
Protocol: JSON-RPC 2.0 over stdin/stdout
Method: Pipe or direct process communication
Encoding: UTF-8
Format: Line-delimited JSON
```

#### Example

```bash
# Create input file
cat > request.json << 'EOF'
{
  "jsonrpc": "2.0",
  "method": "get_server_status",
  "params": {},
  "id": 1
}
EOF

# Send request
python app/main.py < request.json
```

---

## Protocol Details

### MCP (Model Context Protocol)

The server implements **JSON-RPC 2.0** over HTTP or stdio.

#### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "tool_name",
  "params": {
    "input_data": {
      "param1": "value1",
      "param2": 123
    }
  },
  "id": 1
}
```

#### Response Format (Success)

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "data": {}
  },
  "id": 1
}
```

#### Response Format (Error)

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {
      "error_code": "SPECIFIC_ERROR",
      "error_message": "Detailed message",
      "correlation_id": "uuid"
    }
  },
  "id": 1
}
```

### Available Tools

#### Tool 1: `ingest_csv`

**Purpose:** Load CSV documents into vector database

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "ingest_csv",
  "params": {
    "input_data": {
      "file_path": "data/sample_data.csv"
    }
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "documents_processed": 5,
    "chunks_created": 5,
    "embeddings_generated": 5,
    "collection_name": "data/sample_data.csv",
    "processing_time_seconds": 0.28,
    "errors": []
  },
  "id": 1
}
```

#### Tool 2: `query_documents`

**Purpose:** Search documents using natural language

**Request:**
```json
{
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
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": [
    {
      "document_id": "abc123",
      "chunk_id": "chunk-1",
      "content": "Kanishk S: 45.50...",
      "similarity_score": 0.856,
      "metadata": {
        "source_file": "data/uploads/cards.csv",
        "row_number": 2,
        "ingestion_time": "2025-10-24T04:41:43.649425"
      }
    }
  ],
  "id": 2
}
```

#### Tool 3: `get_server_status`

**Purpose:** Check server health

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "get_server_status",
  "params": {},
  "id": 3
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "server_name": "csv-rag-server",
    "version": "1.0.0",
    "status": "running",
    "uptime_seconds": 123.45,
    "components": {
      "csv_parser": "ok",
      "fastembed": "ok",
      "qdrant_client": "ok",
      "langgraph": "ok"
    },
    "last_health_check": "2025-10-24T04:41:23.522615Z"
  },
  "id": 3
}
```

#### Tool 4: `get_http_health` (HTTP Only)

**Purpose:** Detailed HTTP transport health metrics

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "get_http_health",
  "params": {},
  "id": 4
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "healthy",
    "timestamp": "2025-10-24T04:41:23.522615Z",
    "server_name": "csv-rag-server",
    "version": "1.0.0",
    "uptime_seconds": 123.45,
    "components": {
      "csv_parser": "ok",
      "fastembed": "ok",
      "qdrant_client": "ok",
      "langgraph": "ok"
    },
    "http_transport": {
      "transport_mode": "http",
      "host": "0.0.0.0",
      "port": 8080,
      "max_connections": 100,
      "connection_timeout": 300,
      "cors_enabled": true,
      "health_endpoint_enabled": true,
      "connection_stats": {
        "active_connections": 2,
        "total_connections": 157,
        "connection_utilization": 2.0
      },
      "http_metrics": {
        "total_requests": 1523,
        "successful_requests": 1510,
        "failed_requests": 13,
        "avg_response_time": 0.245,
        "error_rate": 0.85,
        "last_updated": "2025-10-24T04:41:23.522615Z"
      }
    }
  },
  "id": 4
}
```

---

## Configuration

### Environment Variables

Create a `.env` file or export variables:

```bash
# Transport
export TRANSPORT_MODE=http
export HTTP_HOST=0.0.0.0
export HTTP_PORT=8080

# Connection
export MAX_CONCURRENT_CONNECTIONS=100
export CONNECTION_TIMEOUT=300
export REQUEST_TIMEOUT=60

# CORS
export ENABLE_CORS=true

# Health
export ENABLE_HEALTH_ENDPOINT=true
export HEALTH_CHECK_PATH=/health

# CSV
export CSV_DATA_DIRECTORY=./data
export CSV_DELIMITER=,
export CSV_ENCODING=utf-8

# Qdrant
export QDRANT_URL=http://localhost:6333
export QDRANT_COLLECTION_NAME=firestore_documents

# Embeddings
export EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
export EMBEDDING_BATCH_SIZE=32
export MAX_CHUNK_SIZE=1000
export CHUNK_OVERLAP=200

# Logging
export ENABLE_LOGFIRE=true
export LOG_LEVEL=INFO
```

### Configuration Priority

1. **Environment Variables** (highest priority)
2. **System Environment**
3. **Default Values** (lowest priority)

### Configuration File (Alternative)

Create `config.yaml`:
```yaml
transport_mode: http
http_host: 0.0.0.0
http_port: 8080
max_concurrent_connections: 100
qdrant_url: http://localhost:6333
qdrant_collection_name: firestore_documents
```

Load with:
```python
from app.config import ServerConfig
config = ServerConfig(_env_file='config.yaml')
```

---

## Client Examples

### Python Client

#### Basic Setup

```python
import httpx
import asyncio

class RAGClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.mcp_endpoint = f"{base_url}/mcp/"
        self.health_endpoint = f"{base_url}/health"

    async def request(self, method: str, params: dict = None, id: int = 1):
        """Send MCP request"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.mcp_endpoint,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or {},
                    "id": id
                }
            )
            return response.json()

    async def ingest_csv(self, file_path: str):
        """Ingest CSV documents"""
        return await self.request(
            "ingest_csv",
            {"input_data": {"file_path": file_path}}
        )

    async def query(self, query: str, max_results: int = 10, score_threshold: float = None):
        """Search documents"""
        return await self.request(
            "query_documents",
            {
                "input_data": {
                    "query": query,
                    "max_results": max_results,
                    "score_threshold": score_threshold
                }
            }
        )

    async def health(self):
        """Check server health"""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.health_endpoint)
            return response.json()

    async def status(self):
        """Get server status"""
        return await self.request("get_server_status")

# Usage
async def main():
    client = RAGClient()

    # Ingest data
    ingest_result = await client.ingest_csv("data/sample_data.csv")
    print("Ingestion:", ingest_result)

    # Search
    search_result = await client.query("lunch with kanishk", max_results=5)
    print("Search results:", search_result)

    # Health check
    health = await client.health()
    print("Health:", health)

# Run
asyncio.run(main())
```

#### Synchronous Example

```python
import requests

client = requests.Session()

# Ingest
response = client.post(
    "http://localhost:8080/mcp/",
    json={
        "jsonrpc": "2.0",
        "method": "ingest_csv",
        "params": {"input_data": {"file_path": "data/sample_data.csv"}},
        "id": 1
    }
)
print(response.json())

# Query
response = client.post(
    "http://localhost:8080/mcp/",
    json={
        "jsonrpc": "2.0",
        "method": "query_documents",
        "params": {
            "input_data": {
                "query": "lunch",
                "max_results": 10
            }
        },
        "id": 2
    }
)
print(response.json())
```

### JavaScript/Node.js Client

```javascript
class RAGClient {
  constructor(baseUrl = "http://localhost:8080") {
    this.baseUrl = baseUrl;
    this.mcpEndpoint = `${baseUrl}/mcp/`;
    this.healthEndpoint = `${baseUrl}/health`;
  }

  async request(method, params = {}, id = 1) {
    const response = await fetch(this.mcpEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: method,
        params: params,
        id: id
      })
    });
    return await response.json();
  }

  async ingestCsv(filePath) {
    return await this.request('ingest_csv', {
      input_data: { file_path: filePath }
    });
  }

  async query(query, maxResults = 10, scoreThreshold = null) {
    return await this.request('query_documents', {
      input_data: {
        query: query,
        max_results: maxResults,
        score_threshold: scoreThreshold
      }
    });
  }

  async health() {
    const response = await fetch(this.healthEndpoint);
    return await response.json();
  }

  async status() {
    return await this.request('get_server_status');
  }
}

// Usage
const client = new RAGClient();

// Ingest
client.ingestCsv('data/sample_data.csv')
  .then(result => console.log('Ingestion:', result));

// Query
client.query('lunch with kanishk', 5)
  .then(results => console.log('Results:', results));

// Health
client.health()
  .then(health => console.log('Health:', health));
```

### cURL Examples

#### Ingest Data

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "ingest_csv",
    "params": {
      "input_data": {
        "file_path": "data/sample_data.csv"
      }
    },
    "id": 1
  }'
```

#### Query Documents

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

#### Check Health

```bash
curl http://localhost:8080/health
```

#### Get Status

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

### Postman Configuration

1. **Create Request:** POST
2. **URL:** `http://localhost:8080/mcp/`
3. **Headers:**
   ```
   Content-Type: application/json
   ```
4. **Body (raw JSON):**
   ```json
   {
     "jsonrpc": "2.0",
     "method": "query_documents",
     "params": {
       "input_data": {
         "query": "your search",
         "max_results": 10
       }
     },
     "id": 1
   }
   ```
5. **Send**

---

## Integration Patterns

### Pattern 1: Simple Search Application

```python
from rag_client import RAGClient

# Initialize
client = RAGClient("http://localhost:8080")

# Search function
async def search_knowledge_base(query: str):
    results = await client.query(query, max_results=10)
    return results['result']

# Use in your app
results = await search_knowledge_base("lunch expenses")
for result in results:
    print(f"Match: {result['content']}")
    print(f"Score: {result['similarity_score']}")
```

### Pattern 2: Document Processing Pipeline

```python
async def process_documents():
    # 1. Ingest new documents
    ingest_response = await client.ingest_csv("data/new_documents.csv")
    if ingest_response['result']['status'] == 'success':
        print(f"Ingested {ingest_response['result']['documents_processed']} docs")

    # 2. Verify ingestion
    status = await client.status()
    if status['result']['components']['qdrant_client'] == 'ok':
        print("Database ready")

    # 3. Perform searches
    queries = ["lunch", "expenses", "kanishk"]
    for query in queries:
        results = await client.query(query)
        print(f"Query '{query}': {len(results['result'])} matches")
```

### Pattern 3: Health Monitoring

```python
import asyncio

async def monitor_server():
    while True:
        try:
            health = await client.health()
            if health['status'] == 'healthy':
                print("✓ Server is healthy")
            elif health['status'] == 'degraded':
                print("⚠ Server is degraded")
            else:
                print("✗ Server is unhealthy")
        except Exception as e:
            print(f"Error: {e}")

        await asyncio.sleep(30)  # Check every 30 seconds

asyncio.run(monitor_server())
```

### Pattern 4: Batch Processing

```python
async def batch_search(queries: list[str]):
    results = {}
    for query in queries:
        try:
            response = await client.query(query, max_results=5)
            results[query] = response['result']
        except Exception as e:
            results[query] = {'error': str(e)}
    return results

# Use
queries = ["lunch", "meeting", "expenses", "kanishk", "food"]
results = await batch_search(queries)
```

---

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to server
```
Error: Connection refused
```

**Solutions:**
```bash
# 1. Check if server is running
ps aux | grep "python.*main.py"

# 2. Check if port is listening
netstat -tuln | grep 8080

# 3. Verify configuration
echo $TRANSPORT_MODE
echo $HTTP_PORT

# 4. Restart server
pkill -f "python.*main.py"
python app/main.py
```

### Port Already in Use

**Problem:**
```
Error: Address already in use
```

**Solution:**
```bash
# Find process using port 8080
lsof -i :8080

# Kill process
kill -9 <PID>

# Or use different port
export HTTP_PORT=8081
python app/main.py
```

### CSV File Not Found

**Problem:**
```
Error: CSV file not found: data/sample.csv
```

**Solution:**
```bash
# Check file exists
ls -la data/sample.csv

# Use relative path from project root
# The working directory matters!
cd /Users/gokulnathanb/Projects/mine/rag_mcp
python app/main.py

# Or use absolute path
curl ... -d '{"file_path": "/full/path/to/sample.csv"}'
```

### Qdrant Connection Error

**Problem:**
```
Error: Cannot connect to Qdrant at http://localhost:6333
```

**Solution:**
```bash
# Start Qdrant with Docker
docker run -d -p 6333:6333 qdrant/qdrant

# Or with Docker Compose
docker-compose up -d qdrant

# Check if running
curl http://localhost:6333/health
```

### Out of Memory

**Problem:**
```
MemoryError: Unable to allocate memory
```

**Solution:**
```bash
# Increase container memory
docker run -m 2g rag-mcp:1.0.0

# Or reduce batch size
export EMBEDDING_BATCH_SIZE=16

# Or reduce max connections
export MAX_CONCURRENT_CONNECTIONS=50
```

### Slow Responses

**Problem:** API responses are slow

**Solutions:**
1. Check network latency: `ping localhost`
2. Monitor server: `curl http://localhost:8080/health`
3. Check Qdrant performance: `curl http://localhost:6333/health`
4. Reduce `max_results` in queries
5. Add score threshold to filter results

### CORS Errors (Web Browsers)

**Problem:**
```
Access to XMLHttpRequest blocked by CORS policy
```

**Solution:**
```bash
# Enable CORS
export ENABLE_CORS=true

# Or configure in code
from app.config import ServerConfig
config = ServerConfig()
config.http_transport.enable_cors = True
config.http_transport.cors_origins = ["http://localhost:3000"]
```

---

## Best Practices

### 1. Connection Management

```python
# ✓ Good: Use connection pooling
async with httpx.AsyncClient() as client:
    response = await client.post(...)

# ✗ Bad: Create new client for each request
client = httpx.AsyncClient()
response = await client.post(...)
```

### 2. Error Handling

```python
# ✓ Good: Handle specific errors
try:
    results = await client.query("test")
except httpx.ConnectError:
    print("Cannot connect to server")
except httpx.TimeoutError:
    print("Request timeout")
except Exception as e:
    print(f"Error: {e}")

# ✗ Bad: Generic error handling
try:
    results = await client.query("test")
except:
    pass  # Ignoring errors
```

### 3. Health Checks

```python
# ✓ Good: Check health before operations
health = await client.health()
if health['status'] == 'healthy':
    results = await client.query("...")

# ✗ Bad: Assume server is healthy
results = await client.query("...")
```

### 4. Request Parameters

```python
# ✓ Good: Use reasonable limits
results = await client.query(
    "lunch",
    max_results=10,  # Reasonable limit
    score_threshold=0.3  # Filter low-quality results
)

# ✗ Bad: No limits
results = await client.query(
    "lunch",
    max_results=10000  # Too many results
)
```

### 5. Batch Operations

```python
# ✓ Good: Batch multiple operations
queries = ["lunch", "expenses", "meeting"]
results = {q: await client.query(q) for q in queries}

# ✗ Bad: Sequential operations without optimization
for query in queries:
    result1 = await client.query(query)
    result2 = await client.query(query)
    result3 = await client.query(query)
```

### 6. Logging

```python
# ✓ Good: Log important operations
import logging
logger = logging.getLogger(__name__)

logger.info(f"Ingesting {len(files)} files")
ingest_result = await client.ingest_csv("data/file.csv")
logger.info(f"Result: {ingest_result['result']['status']}")

# ✗ Bad: No logging
await client.ingest_csv("data/file.csv")
```

### 7. Timeout Configuration

```python
# ✓ Good: Set appropriate timeouts
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(url, json=data)

# ✗ Bad: No timeout (can hang)
async with httpx.AsyncClient() as client:
    response = await client.post(url, json=data)
```

### 8. Data Validation

```python
# ✓ Good: Validate before sending
if not os.path.exists(file_path):
    raise ValueError(f"File not found: {file_path}")
if not file_path.endswith('.csv'):
    raise ValueError("File must be CSV format")

await client.ingest_csv(file_path)

# ✗ Bad: Send without validation
await client.ingest_csv(file_path)
```

---

## Advanced Topics

### Custom Headers

```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8080/mcp/",
        json=request_data,
        headers={
            "Authorization": "Bearer YOUR_TOKEN",
            "X-Custom-Header": "value"
        }
    )
```

### Proxy Support

```python
async with httpx.AsyncClient(
    proxies="http://proxy.example.com:8080"
) as client:
    response = await client.post(...)
```

### Custom Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def query_with_retry(query: str):
    return await client.query(query)
```

### Rate Limiting

```python
from asyncio import Semaphore

semaphore = Semaphore(10)  # Max 10 concurrent requests

async def limited_query(query: str):
    async with semaphore:
        return await client.query(query)
```

---

## Support & Resources

- **Documentation:** See PROJECT_REPORT.md
- **Issues:** Check logs and error messages
- **Configuration:** Review app/config.py
- **Health Endpoint:** `http://localhost:8080/health`

---

## Quick Reference

| Operation | Endpoint | Method |
|-----------|----------|--------|
| Ingest CSV | `/mcp/` | POST |
| Search Docs | `/mcp/` | POST |
| Server Status | `/mcp/` | POST |
| Health Check | `/health` | GET |

**Server Default:**
- Host: `0.0.0.0` (all interfaces)
- Port: `8080`
- Transport: HTTP

**Start Command:**
```bash
export TRANSPORT_MODE=http && python app/main.py
```

---

**Document Generated:** 2025-10-24
**Version:** 1.0.0
**Last Updated:** 2025-10-24
