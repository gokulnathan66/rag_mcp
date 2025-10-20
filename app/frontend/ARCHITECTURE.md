# Web UI Architecture

## System Overview

The RAG MCP Server Web UI provides a browser-based interface for CSV ingestion and document querying. It's built as a separate FastAPI application that uses the same backend components as the MCP server.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (User)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Upload     │  │    Query     │  │    Status    │      │
│  │     UI       │  │      UI      │  │      UI      │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          │ HTTP POST        │ HTTP POST        │ HTTP GET
          │ /api/upload-csv  │ /api/query       │ /api/health
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────────┐
│                    FastAPI Web Server                        │
│                      (app/web_api.py)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Upload     │  │    Query     │  │    Health    │      │
│  │  Endpoint    │  │   Endpoint   │  │   Endpoint   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          │ Direct calls     │                  │
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────────┐
│                    Orchestrator (LangGraph)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Ingestion Workflow                      │   │
│  │  Parse CSV → Chunk → Embed → Store in Qdrant        │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Query Workflow                          │   │
│  │  Embed Query → Search Qdrant → Format Results       │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  CSV Parser  │  │   FastEmbed  │  │    Qdrant    │
│              │  │   (ONNX)     │  │   Client     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       ▼                 ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  CSV Files   │  │  Embedding   │  │   Qdrant     │
│  (uploads/)  │  │   Models     │  │   Database   │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Data Flow

### CSV Upload Flow

```
1. User selects CSV file in browser
   ↓
2. JavaScript sends file via FormData (multipart/form-data)
   ↓
3. FastAPI receives file and saves to data/uploads/
   ↓
4. FastAPI calls orchestrator.ingest_csv(file_path)
   ↓
5. Orchestrator runs LangGraph workflow:
   a. CSV Parser reads file → List[CSVDocument]
   b. Embedder chunks documents → List[DocumentChunk]
   c. Embedder generates embeddings → List[DocumentEmbedding]
   d. Qdrant Client stores vectors → Success/Failure
   ↓
6. FastAPI returns IngestionStatus to browser
   ↓
7. JavaScript displays results with statistics
```

### Query Flow

```
1. User enters query in browser
   ↓
2. JavaScript sends query via JSON (application/json)
   ↓
3. FastAPI receives query parameters
   ↓
4. FastAPI calls orchestrator.query(query, max_results, threshold)
   ↓
5. Orchestrator runs LangGraph workflow:
   a. Embedder converts query to vector
   b. Qdrant Client performs similarity search
   c. Results assembled with metadata
   ↓
6. FastAPI returns List[QueryResult] to browser
   ↓
7. JavaScript displays results with scores and metadata
```

## Key Design Decisions

### 1. Separate Web Server vs MCP Server

**Why separate?**
- MCP server uses stdio/JSON-RPC protocol (not HTTP)
- Web UI needs HTTP endpoints for browser access
- Different use cases: MCP for tool integration, Web for human users

**How they relate:**
- Both use the same Orchestrator and backend components
- Web server is essentially an HTTP wrapper around the Orchestrator
- Can run simultaneously on different ports

### 2. File Upload Strategy

**Why save to disk first?**
- CSV Parser expects file paths, not file objects
- Allows re-processing without re-uploading
- Enables file management and history
- Consistent with MCP server's file-based approach

**Alternative considered:**
- Stream processing: More complex, no re-processing capability
- In-memory: Limited by RAM, no persistence

### 3. Frontend Architecture

**Why vanilla JavaScript?**
- No build step required
- Simple deployment (just serve static files)
- Easy to understand and modify
- Minimal dependencies

**Alternative considered:**
- React/Vue: Overkill for this simple UI
- Would add build complexity

### 4. API Design

**RESTful endpoints:**
- `POST /api/upload-csv` - File upload (multipart/form-data)
- `POST /api/query` - Query documents (JSON)
- `GET /api/health` - Health check
- `GET /api/uploaded-files` - List files

**Why REST over GraphQL?**
- Simpler for this use case
- Better browser support
- Easier to test with curl/Postman

## Security Considerations

### Current Implementation (Development)

- No authentication
- No rate limiting
- No file size limits
- No input sanitization beyond basic validation

### Production Recommendations

1. **Authentication & Authorization**
   ```python
   from fastapi import Depends, HTTPException
   from fastapi.security import HTTPBearer
   
   security = HTTPBearer()
   
   @app.post("/api/upload-csv")
   async def upload_csv(
       file: UploadFile,
       token: str = Depends(security)
   ):
       # Verify token
       pass
   ```

2. **Rate Limiting**
   ```python
   from slowapi import Limiter
   
   limiter = Limiter(key_func=get_remote_address)
   
   @app.post("/api/upload-csv")
   @limiter.limit("5/minute")
   async def upload_csv(...):
       pass
   ```

3. **File Validation**
   ```python
   MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
   ALLOWED_EXTENSIONS = {".csv"}
   
   def validate_file(file: UploadFile):
       # Check size, extension, content
       pass
   ```

4. **CORS Configuration**
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://yourdomain.com"],
       allow_methods=["GET", "POST"],
       allow_headers=["*"],
   )
   ```

## Performance Considerations

### Current Optimizations

1. **Async Operations**: All I/O operations are async
2. **Batch Processing**: Embeddings generated in batches
3. **Streaming**: Large files processed in chunks
4. **Connection Pooling**: Qdrant client reuses connections

### Potential Improvements

1. **Caching**
   - Cache frequently queried embeddings
   - Cache file metadata

2. **Background Tasks**
   - Process large files in background
   - Return immediately with job ID
   - Poll for completion

3. **Compression**
   - Compress API responses
   - Use gzip middleware

4. **CDN**
   - Serve static files from CDN
   - Cache frontend assets

## Monitoring & Debugging

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Logs include:
# - Request/response details
# - Processing times
# - Error stack traces
# - Component health status
```

### Health Checks

```python
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "components": {
            "csv_parser": "ok",
            "embedder": "ok",
            "qdrant": "ok"
        }
    }
```

### Metrics (Future)

- Request count and latency
- Upload success/failure rate
- Query response times
- Qdrant vector count
- Disk usage

## Testing Strategy

### Unit Tests

```python
# Test individual endpoints
async def test_upload_csv():
    response = await client.post(
        "/api/upload-csv",
        files={"file": ("test.csv", csv_content)}
    )
    assert response.status_code == 200
```

### Integration Tests

```python
# Test full workflow
async def test_upload_and_query():
    # Upload CSV
    upload_response = await upload_csv(test_file)
    
    # Query documents
    query_response = await query_documents("test query")
    
    # Verify results
    assert len(query_response) > 0
```

### E2E Tests

- Selenium/Playwright for browser testing
- Test user workflows
- Verify UI interactions

## Deployment Options

### 1. Docker Compose (Recommended)

```bash
docker-compose up -d
```

Pros: Easy, reproducible, includes Qdrant
Cons: Requires Docker

### 2. Standalone Python

```bash
python -m app.web_server
```

Pros: Simple, no Docker needed
Cons: Manual Qdrant setup

### 3. Cloud Deployment

- AWS: ECS/Fargate + RDS for Qdrant
- GCP: Cloud Run + Cloud SQL
- Azure: Container Instances + Cosmos DB

### 4. Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-web-ui
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: web-ui
        image: rag-web-ui:latest
        ports:
        - containerPort: 8000
```

## Future Enhancements

1. **User Management**
   - Multi-user support
   - User-specific collections
   - Access control

2. **Advanced Features**
   - Batch upload (multiple files)
   - Scheduled re-indexing
   - Export results to CSV/JSON
   - Query history

3. **UI Improvements**
   - Dark mode
   - Drag-and-drop upload
   - Real-time progress bars
   - Result highlighting

4. **Analytics**
   - Usage statistics
   - Popular queries
   - Performance metrics dashboard

## Conclusion

The Web UI provides a user-friendly interface to the RAG MCP Server's capabilities. It's designed to be simple, maintainable, and extensible while providing a solid foundation for production use with appropriate security and performance enhancements.
