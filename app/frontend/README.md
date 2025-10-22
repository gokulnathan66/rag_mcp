# RAG MCP Server Web UI

A simple web interface for uploading CSV files and querying documents using the RAG MCP Server.

## Features

- **CSV Upload**: Upload CSV files directly through the browser
- **Document Query**: Search documents using natural language queries
- **Real-time Status**: Monitor server health and component status
- **File Management**: View uploaded files and their metadata
- **Results Display**: See query results with similarity scores and metadata

## Architecture

```
Browser (Frontend)
    ↓ HTTP
FastAPI Web Server (app/web_api.py)
    ↓ Direct calls
Orchestrator (LangGraph)
    ↓
CSV Parser → FastEmbed → Qdrant
```

## Running the Web UI

### Option 1: Standalone Web Server

Run the web server separately from the MCP server:

```bash
python -m app.web_server
```

Then open http://localhost:8080 in your browser.

### Option 2: With Docker Compose

```bash
docker-compose up web-ui
```

Access at http://localhost:8080

## API Endpoints

### POST /api/upload-csv
Upload and ingest a CSV file.

**Request**: multipart/form-data with file
**Response**:
```json
{
  "status": "success",
  "message": "File uploaded and ingested",
  "file_path": "/path/to/file.csv",
  "ingestion_result": {
    "status": "success",
    "documents_processed": 100,
    "chunks_created": 250,
    "embeddings_generated": 250,
    "processing_time_seconds": 5.2
  }
}
```

### POST /api/query
Query documents using natural language.

**Request**:
```json
{
  "query": "What are the main topics?",
  "max_results": 10,
  "score_threshold": 0.7
}
```

**Response**:
```json
[
  {
    "document_id": "abc123",
    "chunk_id": "xyz789",
    "content": "Document content...",
    "similarity_score": 0.85,
    "metadata": {
      "source_file": "data.csv",
      "row_number": 42
    }
  }
]
```

### GET /api/health
Check server health status.

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

### GET /api/uploaded-files
List all uploaded CSV files.

**Response**:
```json
{
  "files": [
    {
      "filename": "data.csv",
      "size_bytes": 1024000,
      "uploaded_at": 1698765432.0
    }
  ]
}
```

## File Structure

```
app/frontend/
├── index.html      # Main HTML page
├── app.js          # JavaScript application logic
├── styles.css      # Styling
└── README.md       # This file

app/
├── web_api.py      # FastAPI endpoints
└── web_server.py   # Standalone server runner
```

## Development

The frontend is a simple vanilla JavaScript application with no build step required. Just edit the files and refresh your browser.

### Adding New Features

1. **Add API endpoint** in `app/web_api.py`
2. **Add UI elements** in `app/frontend/index.html`
3. **Add JavaScript logic** in `app/frontend/app.js`
4. **Style components** in `app/frontend/styles.css`

## Configuration

The web server uses the same configuration as the MCP server (from environment variables or `.env` file):

- `CSV_DATA_DIRECTORY`: Where uploaded files are stored
- `QDRANT_URL`: Qdrant server URL
- `QDRANT_COLLECTION_NAME`: Collection name for vectors
- `EMBEDDING_MODEL_NAME`: FastEmbed model to use

## Security Considerations

For production deployment:

1. **Add authentication**: Implement user authentication/authorization
2. **File validation**: Validate file size, type, and content
3. **Rate limiting**: Prevent abuse of upload/query endpoints
4. **CORS configuration**: Configure allowed origins
5. **HTTPS**: Use TLS/SSL for encrypted communication
6. **Input sanitization**: Validate and sanitize all user inputs

## Troubleshooting

### Upload fails
- Check CSV file format (valid CSV with headers)
- Ensure `CSV_DATA_DIRECTORY` exists and is writable
- Check server logs for detailed error messages

### Query returns no results
- Ensure CSV files have been uploaded and ingested
- Check Qdrant connection and collection status
- Try broader queries or lower score thresholds

### Server health shows degraded
- Check Qdrant is running: `docker ps | grep qdrant`
- Verify Qdrant URL in configuration
- Check network connectivity between services
