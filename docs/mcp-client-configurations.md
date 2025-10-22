# MCP Client Configuration Examples

This document provides example configurations for connecting MCP clients to the RAG MCP Server using HTTP transport.

## Overview

The RAG MCP Server supports HTTP transport mode, allowing remote clients to connect over HTTP. This enables integration with MCP clients like Cursor IDE, custom applications, and command-line tools.

**Server Endpoints:**
- MCP Protocol: `http://localhost:8000/mcp/`
- Health Check: `http://localhost:8000/health`

## Cursor IDE Integration

### Basic mcp.json Configuration

Create or update your `mcp.json` configuration file:

```json
{
  "mcpServers": {
    "csv-rag-server": {
      "command": "python",
      "args": [
        "-c",
        "import requests; import json; import sys; response = requests.post('http://localhost:8000/mcp/', json=json.loads(sys.stdin.read())); print(json.dumps(response.json()))"
      ],
      "env": {
        "MCP_SERVER_URL": "http://localhost:8000/mcp/"
      }
    }
  }
}
```

### Advanced mcp.json with Error Handling

```json
{
  "mcpServers": {
    "csv-rag-server": {
      "command": "python",
      "args": [
        "-c",
        "import requests; import json; import sys; import time; data = json.loads(sys.stdin.read()); max_retries = 3; for attempt in range(max_retries): try: response = requests.post('http://localhost:8000/mcp/', json=data, timeout=30); response.raise_for_status(); print(json.dumps(response.json())); break; except Exception as e: time.sleep(1); if attempt == max_retries - 1: print(json.dumps({'error': {'code': 'CONNECTION_ERROR', 'message': str(e)}})); sys.exit(1)"
      ],
      "env": {
        "MCP_SERVER_URL": "http://localhost:8000/mcp/",
        "MCP_TIMEOUT": "30",
        "MCP_MAX_RETRIES": "3"
      }
    }
  }
}
```

### Remote Server Configuration

For connecting to a remote RAG MCP Server:

```json
{
  "mcpServers": {
    "csv-rag-server-remote": {
      "command": "python",
      "args": [
        "-c",
        "import requests; import json; import sys; response = requests.post('http://your-server-host:8000/mcp/', json=json.loads(sys.stdin.read()), timeout=60); print(json.dumps(response.json()))"
      ],
      "env": {
        "MCP_SERVER_URL": "http://your-server-host:8000/mcp/",
        "MCP_TIMEOUT": "60"
      }
    }
  }
}
```

## curl-based Client Examples

### Basic MCP Tool Call

Test the `get_server_status` tool:

```bash
curl -X POST http://localhost:8000/mcp/ \
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

### CSV Ingestion Example

Ingest a CSV file:

```bash
curl -X POST http://localhost:8000/mcp/ \
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

### Document Query Example

Query documents:

```bash
curl -X POST http://localhost:8000/mcp/ \
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

### Health Check Example

Check server health:

```bash
curl -X GET http://localhost:8000/health
```

## Python Client Example

### Simple Python MCP Client

```python
import requests
import json
from typing import Dict, Any, Optional

class RAGMCPClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.mcp_url = f"{self.base_url}/mcp/"
        self.health_url = f"{self.base_url}/health"
        self.request_id = 1
    
    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an MCP JSON-RPC request."""
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        self.request_id += 1
        
        response = requests.post(
            self.mcp_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_server_status(self) -> Dict[str, Any]:
        """Get server status."""
        return self._make_request("tools/call", {
            "name": "get_server_status",
            "arguments": {}
        })
    
    def ingest_csv(self, file_path: str) -> Dict[str, Any]:
        """Ingest a CSV file."""
        return self._make_request("tools/call", {
            "name": "ingest_csv",
            "arguments": {"file_path": file_path}
        })
    
    def query_documents(self, query: str, max_results: int = 10, 
                       score_threshold: Optional[float] = None) -> Dict[str, Any]:
        """Query documents."""
        args = {"query": query, "max_results": max_results}
        if score_threshold is not None:
            args["score_threshold"] = score_threshold
        
        return self._make_request("tools/call", {
            "name": "query_documents",
            "arguments": args
        })
    
    def get_health(self) -> Dict[str, Any]:
        """Get health status via HTTP endpoint."""
        response = requests.get(self.health_url, timeout=10)
        response.raise_for_status()
        return response.json()

# Usage example
if __name__ == "__main__":
    client = RAGMCPClient()
    
    # Check server status
    status = client.get_server_status()
    print("Server Status:", json.dumps(status, indent=2))
    
    # Check health
    health = client.get_health()
    print("Health Status:", json.dumps(health, indent=2))
    
    # Ingest CSV (example)
    # result = client.ingest_csv("./data/sample_products.csv")
    # print("Ingestion Result:", json.dumps(result, indent=2))
    
    # Query documents (example)
    # results = client.query_documents("What products are available?", max_results=5)
    # print("Query Results:", json.dumps(results, indent=2))
```

## Node.js Client Example

### Simple Node.js MCP Client

```javascript
const axios = require('axios');

class RAGMCPClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.mcpUrl = `${this.baseUrl}/mcp/`;
        this.healthUrl = `${this.baseUrl}/health`;
        this.requestId = 1;
    }

    async makeRequest(method, params) {
        const payload = {
            jsonrpc: '2.0',
            id: this.requestId++,
            method: method,
            params: params
        };

        try {
            const response = await axios.post(this.mcpUrl, payload, {
                headers: { 'Content-Type': 'application/json' },
                timeout: 30000
            });
            return response.data;
        } catch (error) {
            throw new Error(`MCP request failed: ${error.message}`);
        }
    }

    async getServerStatus() {
        return this.makeRequest('tools/call', {
            name: 'get_server_status',
            arguments: {}
        });
    }

    async ingestCsv(filePath) {
        return this.makeRequest('tools/call', {
            name: 'ingest_csv',
            arguments: { file_path: filePath }
        });
    }

    async queryDocuments(query, maxResults = 10, scoreThreshold = null) {
        const args = { query, max_results: maxResults };
        if (scoreThreshold !== null) {
            args.score_threshold = scoreThreshold;
        }

        return this.makeRequest('tools/call', {
            name: 'query_documents',
            arguments: args
        });
    }

    async getHealth() {
        try {
            const response = await axios.get(this.healthUrl, { timeout: 10000 });
            return response.data;
        } catch (error) {
            throw new Error(`Health check failed: ${error.message}`);
        }
    }
}

// Usage example
async function main() {
    const client = new RAGMCPClient();

    try {
        // Check server status
        const status = await client.getServerStatus();
        console.log('Server Status:', JSON.stringify(status, null, 2));

        // Check health
        const health = await client.getHealth();
        console.log('Health Status:', JSON.stringify(health, null, 2));

        // Example usage (uncomment to use):
        // const result = await client.ingestCsv('./data/sample_products.csv');
        // console.log('Ingestion Result:', JSON.stringify(result, null, 2));

        // const results = await client.queryDocuments('What products are available?', 5);
        // console.log('Query Results:', JSON.stringify(results, null, 2));

    } catch (error) {
        console.error('Error:', error.message);
    }
}

if (require.main === module) {
    main();
}

module.exports = RAGMCPClient;
```

## Docker-based Client Configuration

### Using Docker for MCP Client

Create a `docker-compose.client.yml` for client testing:

```yaml
version: '3.8'
services:
  mcp-client-test:
    image: python:3.11-slim
    volumes:
      - ./client-scripts:/app/scripts
      - ./data:/app/data:ro
    working_dir: /app
    command: >
      bash -c "
        pip install requests &&
        python scripts/test_mcp_client.py
      "
    environment:
      - MCP_SERVER_URL=http://rag-mcp-server:8000/mcp/
      - MCP_HEALTH_URL=http://rag-mcp-server:8000/health
    depends_on:
      - rag-mcp-server
    networks:
      - mcp-network

networks:
  mcp-network:
    external: true
```

### Client Test Script

Create `client-scripts/test_mcp_client.py`:

```python
#!/usr/bin/env python3
import os
import requests
import json
import time

def test_mcp_connection():
    """Test MCP server connection and basic functionality."""
    
    mcp_url = os.getenv('MCP_SERVER_URL', 'http://localhost:8000/mcp/')
    health_url = os.getenv('MCP_HEALTH_URL', 'http://localhost:8000/health')
    
    print(f"Testing MCP server at: {mcp_url}")
    print(f"Health endpoint at: {health_url}")
    
    # Test health endpoint
    try:
        health_response = requests.get(health_url, timeout=10)
        health_response.raise_for_status()
        health_data = health_response.json()
        print("✓ Health check passed")
        print(f"  Status: {health_data.get('status')}")
        print(f"  Version: {health_data.get('version')}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False
    
    # Test MCP server status
    try:
        status_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_server_status",
                "arguments": {}
            }
        }
        
        status_response = requests.post(
            mcp_url,
            json=status_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        status_response.raise_for_status()
        status_data = status_response.json()
        
        if 'result' in status_data:
            print("✓ MCP server status check passed")
            result = status_data['result']
            print(f"  Server: {result.get('server_name')} v{result.get('version')}")
            print(f"  Status: {result.get('status')}")
            print(f"  Components: {result.get('components')}")
        else:
            print(f"✗ MCP server status check failed: {status_data}")
            return False
            
    except Exception as e:
        print(f"✗ MCP server status check failed: {e}")
        return False
    
    print("✓ All tests passed!")
    return True

if __name__ == "__main__":
    success = test_mcp_connection()
    exit(0 if success else 1)
```

## Environment Variables

### Client Configuration via Environment Variables

```bash
# Server connection
export MCP_SERVER_URL="http://localhost:8000/mcp/"
export MCP_HEALTH_URL="http://localhost:8000/health"

# Request settings
export MCP_TIMEOUT="30"
export MCP_MAX_RETRIES="3"
export MCP_RETRY_DELAY="1"

# Authentication (if implemented)
export MCP_API_KEY="your-api-key"
export MCP_AUTH_HEADER="Authorization"
```

### Using Environment Variables in mcp.json

```json
{
  "mcpServers": {
    "csv-rag-server": {
      "command": "python",
      "args": [
        "-c",
        "import os; import requests; import json; import sys; url = os.getenv('MCP_SERVER_URL', 'http://localhost:8000/mcp/'); timeout = int(os.getenv('MCP_TIMEOUT', '30')); response = requests.post(url, json=json.loads(sys.stdin.read()), timeout=timeout); print(json.dumps(response.json()))"
      ],
      "env": {
        "MCP_SERVER_URL": "${MCP_SERVER_URL:-http://localhost:8000/mcp/}",
        "MCP_TIMEOUT": "${MCP_TIMEOUT:-30}"
      }
    }
  }
}
```

## Connection Methods Summary

| Method | Use Case | Pros | Cons |
|--------|----------|------|------|
| Cursor IDE mcp.json | IDE integration | Native MCP support | Requires Python/requests |
| curl | Testing/debugging | Simple, no dependencies | Manual JSON crafting |
| Python client | Custom applications | Full control, error handling | Requires Python |
| Node.js client | Web applications | JavaScript ecosystem | Requires Node.js |
| Docker client | Containerized testing | Isolated environment | Docker overhead |

## Next Steps

1. Choose the appropriate client method for your use case
2. Configure the server URL and authentication (if needed)
3. Test the connection using the health endpoint
4. Start using the MCP tools for CSV ingestion and document queries

For troubleshooting and advanced configuration, see the [Client Setup Documentation](client-setup-guide.md).