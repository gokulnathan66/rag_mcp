# RAG MCP Server - Documentation

This directory contains comprehensive documentation for the RAG MCP Server HTTP transport feature.

## Documents

### Client Configuration and Setup

- **[MCP Client Configuration Examples](mcp-client-configurations.md)** - Comprehensive examples of MCP client configurations for various platforms and use cases
- **[Client Setup Guide](client-setup-guide.md)** - Step-by-step instructions for setting up and configuring MCP clients

### Examples

- **[Client Examples](../examples/mcp-clients/)** - Ready-to-use client implementations in Python, Node.js, curl, and Cursor IDE configurations

## Quick Links

### For Cursor IDE Users
- [Cursor IDE mcp.json Configuration](mcp-client-configurations.md#cursor-ide-integration)
- [Example mcp.json files](../examples/mcp-clients/cursor-ide/)

### For Developers
- [Python Client Example](../examples/mcp-clients/python/simple_client.py)
- [Node.js Client Example](../examples/mcp-clients/nodejs/simple-client.js)
- [curl Client Script](../examples/mcp-clients/curl/test-client.sh)

### For System Administrators
- [HTTP Transport Configuration](client-setup-guide.md#server-configuration)
- [Docker Deployment](client-setup-guide.md#docker-based-client-configuration)
- [Troubleshooting Guide](client-setup-guide.md#troubleshooting-guide)

## Getting Started

1. **Start the RAG MCP Server with HTTP transport:**
   ```bash
   export TRANSPORT_MODE=http
   export HTTP_HOST=0.0.0.0
   export HTTP_PORT=8080
   python -m app.main
   ```

2. **Test the connection:**
   ```bash
   curl http://localhost:8080/health
   ```

3. **Choose your client method:**
   - **Cursor IDE**: Use the [mcp.json examples](../examples/mcp-clients/cursor-ide/)
   - **Python**: Use the [Python client](../examples/mcp-clients/python/simple_client.py)
   - **Node.js**: Use the [Node.js client](../examples/mcp-clients/nodejs/simple-client.js)
   - **curl**: Use the [curl script](../examples/mcp-clients/curl/test-client.sh)

4. **Follow the setup guide:**
   - Read the [Client Setup Guide](client-setup-guide.md) for detailed instructions
   - Check the [troubleshooting section](client-setup-guide.md#troubleshooting-guide) if you encounter issues

## Available MCP Tools

The RAG MCP Server provides these tools via HTTP transport:

### `get_server_status`
Get the current status of the server and its components.

**Example:**
```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_server_status",
      "arguments": {}
    }
  }'
```

### `ingest_csv`
Ingest documents from a CSV file into the vector database.

**Parameters:**
- `file_path` (string): Path to the CSV file

**Example:**
```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "ingest_csv",
      "arguments": {
        "file_path": "./data/sample_products.csv"
      }
    }
  }'
```

### `query_documents`
Query documents using natural language and vector similarity search.

**Parameters:**
- `query` (string): Natural language query
- `max_results` (integer, optional): Maximum number of results (default: 10)
- `score_threshold` (float, optional): Minimum similarity score

**Example:**
```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "query_documents",
      "arguments": {
        "query": "What products are available?",
        "max_results": 5,
        "score_threshold": 0.7
      }
    }
  }'
```

### `get_http_health` (HTTP transport only)
Get HTTP transport-specific health information.

**Example:**
```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "get_http_health",
      "arguments": {}
    }
  }'
```

## Health Check Endpoint

The server also provides a direct HTTP health check endpoint:

```bash
curl http://localhost:8080/health
```

This endpoint returns comprehensive health information including:
- Overall server status
- Component health status
- HTTP transport metrics
- Connection statistics

## Configuration Options

### Environment Variables

```bash
# Transport Mode
TRANSPORT_MODE=http                    # Enable HTTP transport

# HTTP Server Settings
HTTP_HOST=127.0.0.1                   # Server host
HTTP_PORT=8080                        # Server port

# Connection Management
MAX_CONCURRENT_CONNECTIONS=100        # Max concurrent connections
CONNECTION_TIMEOUT=300                # Connection timeout (seconds)
REQUEST_TIMEOUT=60                    # Request timeout (seconds)

# CORS Configuration
ENABLE_CORS=true                      # Enable CORS
CORS_ORIGINS=*                        # Allowed origins

# Health Check
ENABLE_HEALTH_ENDPOINT=true           # Enable /health endpoint
HEALTH_CHECK_PATH=/health             # Health check path
```

### Docker Configuration

```yaml
version: '3.8'
services:
  rag-mcp-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - TRANSPORT_MODE=http
      - HTTP_HOST=0.0.0.0
      - HTTP_PORT=8080
      - CSV_DATA_DIRECTORY=/app/data
      - QDRANT_URL=http://qdrant:6333
    volumes:
      - ./data:/app/data:ro
```

## Support

### Documentation
- [Client Setup Guide](client-setup-guide.md) - Comprehensive setup instructions
- [MCP Client Configurations](mcp-client-configurations.md) - Configuration examples
- [Client Examples](../examples/mcp-clients/) - Working code examples

### Troubleshooting
- [Connection Issues](client-setup-guide.md#connection-refused)
- [Timeout Problems](client-setup-guide.md#timeout-errors)
- [Configuration Errors](client-setup-guide.md#http-503-service-unavailable)
- [Network Issues](client-setup-guide.md#network-configuration-issues)

### Community
- Check the project repository for issues and discussions
- Review the troubleshooting guide for common problems
- Test with the provided example clients

## Contributing

To contribute to the documentation:

1. Follow the existing documentation structure
2. Include practical examples and code snippets
3. Test all examples with the actual server
4. Update this README when adding new documents
5. Ensure cross-references are accurate

## License

This documentation is provided under the same license as the RAG MCP Server project.