# RAG MCP Server - Client Setup Guide

This guide provides step-by-step instructions for setting up and configuring MCP clients to connect to the RAG MCP Server using HTTP transport.

## Prerequisites

Before setting up MCP clients, ensure you have:

1. **RAG MCP Server running with HTTP transport enabled**
2. **Network connectivity** to the server
3. **Required client dependencies** (Python, Node.js, or curl)

## Server Configuration

### HTTP Transport Configuration Options

The RAG MCP Server supports the following HTTP transport configuration options:

#### Environment Variables

```bash
# Transport Mode
TRANSPORT_MODE=http                    # Enable HTTP transport (default: "default")

# HTTP Server Settings
HTTP_HOST=127.0.0.1                   # Server host (default: "127.0.0.1")
HTTP_PORT=8080                        # Server port (default: 8080)

# Connection Management
MAX_CONCURRENT_CONNECTIONS=100        # Max concurrent connections (default: 100)
CONNECTION_TIMEOUT=300                # Connection timeout in seconds (default: 300)
REQUEST_TIMEOUT=60                    # Request timeout in seconds (default: 60)

# CORS Configuration
ENABLE_CORS=true                      # Enable CORS (default: true)
CORS_ORIGINS=*                        # Allowed origins (default: "*")

# Health Check
ENABLE_HEALTH_ENDPOINT=true           # Enable /health endpoint (default: true)
HEALTH_CHECK_PATH=/health             # Health check path (default: "/health")
```

#### Configuration File (config.py)

```python
from app.config import ServerConfig, HTTPTransportConfig

# Create configuration
config = ServerConfig(
    transport_mode="http",
    http_transport=HTTPTransportConfig(
        enable_http_transport=True,
        http_host="0.0.0.0",  # Bind to all interfaces
        http_port=8080,
        max_concurrent_connections=100,
        connection_timeout=300,
        request_timeout=60,
        enable_cors=True,
        cors_origins=["*"],
        enable_health_endpoint=True,
        health_check_path="/health"
    )
)
```

### Starting the Server with HTTP Transport

#### Method 1: Environment Variables

```bash
# Set environment variables
export TRANSPORT_MODE=http
export HTTP_HOST=0.0.0.0
export HTTP_PORT=8080

# Start the server
python -m app.main
```

#### Method 2: Docker Compose

```yaml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage

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
    depends_on:
      - qdrant
```

#### Method 3: Direct Python Execution

```python
from app.main import main
from app.config import ServerConfig
import os

# Set configuration
os.environ['TRANSPORT_MODE'] = 'http'
os.environ['HTTP_HOST'] = '0.0.0.0'
os.environ['HTTP_PORT'] = '8080'

# Start server
main()
```

## Client Setup Instructions

### 1. Cursor IDE Setup

#### Step 1: Locate mcp.json Configuration

Find your Cursor IDE MCP configuration file:

- **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json`
- **Windows**: `%APPDATA%\Cursor\User\globalStorage\rooveterinaryinc.roo-cline\settings\cline_mcp_settings.json`
- **Linux**: `~/.config/Cursor/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json`

Or create a new `mcp.json` file in your project directory.

#### Step 2: Add RAG MCP Server Configuration

Add the following configuration to your `mcp.json`:

```json
{
  "mcpServers": {
    "csv-rag-server": {
      "command": "python",
      "args": [
        "-c",
        "import requests; import json; import sys; response = requests.post('http://localhost:8080/mcp/', json=json.loads(sys.stdin.read())); print(json.dumps(response.json()))"
      ],
      "env": {
        "MCP_SERVER_URL": "http://localhost:8080/mcp/"
      }
    }
  }
}
```

#### Step 3: Install Python Dependencies

Ensure Python and requests are available:

```bash
pip install requests
```

#### Step 4: Test Connection

1. Restart Cursor IDE
2. Open the MCP panel
3. Verify "csv-rag-server" appears in the server list
4. Test by calling a tool (e.g., `get_server_status`)

### 2. Python Client Setup

#### Step 1: Install Dependencies

```bash
pip install requests
```

#### Step 2: Create Client Script

Create `mcp_client.py`:

```python
import requests
import json
from typing import Dict, Any, Optional

class RAGMCPClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
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
        
        try:
            response = requests.post(
                self.mcp_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"MCP request failed: {e}")
    
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

# Usage
if __name__ == "__main__":
    client = RAGMCPClient("http://localhost:8080")
    
    # Test connection
    try:
        status = client.get_server_status()
        print("Connected successfully!")
        print(f"Server: {status['result']['server_name']}")
        print(f"Status: {status['result']['status']}")
    except Exception as e:
        print(f"Connection failed: {e}")
```

#### Step 3: Test Connection

```bash
python mcp_client.py
```

### 3. Node.js Client Setup

#### Step 1: Install Dependencies

```bash
npm install axios
```

#### Step 2: Create Client Module

Create `mcp-client.js`:

```javascript
const axios = require('axios');

class RAGMCPClient {
    constructor(baseUrl = 'http://localhost:8080') {
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
}

module.exports = RAGMCPClient;

// Test if run directly
if (require.main === module) {
    async function test() {
        const client = new RAGMCPClient();
        try {
            const status = await client.getServerStatus();
            console.log('Connected successfully!');
            console.log(`Server: ${status.result.server_name}`);
            console.log(`Status: ${status.result.status}`);
        } catch (error) {
            console.error('Connection failed:', error.message);
        }
    }
    test();
}
```

#### Step 3: Test Connection

```bash
node mcp-client.js
```

### 4. curl Client Setup

#### Basic Tool Calls

Test server status:
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

Test health endpoint:
```bash
curl -X GET http://localhost:8080/health
```

#### Scripted curl Client

Create `curl-client.sh`:

```bash
#!/bin/bash

# Configuration
MCP_URL="${MCP_SERVER_URL:-http://localhost:8080/mcp/}"
HEALTH_URL="${MCP_HEALTH_URL:-http://localhost:8080/health}"
TIMEOUT=30

# Function to make MCP requests
mcp_request() {
    local method="$1"
    local tool_name="$2"
    local arguments="$3"
    
    curl -s -X POST "$MCP_URL" \
        -H "Content-Type: application/json" \
        -m "$TIMEOUT" \
        -d "{
            \"jsonrpc\": \"2.0\",
            \"id\": $(date +%s),
            \"method\": \"$method\",
            \"params\": {
                \"name\": \"$tool_name\",
                \"arguments\": $arguments
            }
        }"
}

# Function to check health
check_health() {
    curl -s -X GET "$HEALTH_URL" -m 10
}

# Test functions
test_connection() {
    echo "Testing connection to $MCP_URL"
    
    # Check health
    echo "Checking health..."
    health_result=$(check_health)
    if [ $? -eq 0 ]; then
        echo "✓ Health check passed"
        echo "$health_result" | jq '.'
    else
        echo "✗ Health check failed"
        return 1
    fi
    
    # Check server status
    echo "Checking server status..."
    status_result=$(mcp_request "tools/call" "get_server_status" "{}")
    if [ $? -eq 0 ]; then
        echo "✓ Server status check passed"
        echo "$status_result" | jq '.'
    else
        echo "✗ Server status check failed"
        return 1
    fi
}

# Usage examples
case "${1:-test}" in
    "test")
        test_connection
        ;;
    "status")
        mcp_request "tools/call" "get_server_status" "{}"
        ;;
    "health")
        check_health
        ;;
    "ingest")
        if [ -z "$2" ]; then
            echo "Usage: $0 ingest <file_path>"
            exit 1
        fi
        mcp_request "tools/call" "ingest_csv" "{\"file_path\": \"$2\"}"
        ;;
    "query")
        if [ -z "$2" ]; then
            echo "Usage: $0 query <query_text> [max_results]"
            exit 1
        fi
        max_results="${3:-10}"
        mcp_request "tools/call" "query_documents" "{\"query\": \"$2\", \"max_results\": $max_results}"
        ;;
    *)
        echo "Usage: $0 {test|status|health|ingest <file>|query <text> [max_results]}"
        exit 1
        ;;
esac
```

Make it executable and test:
```bash
chmod +x curl-client.sh
./curl-client.sh test
```

## Connection Verification

### 1. Health Check Verification

Test the health endpoint:

```bash
curl -X GET http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "server_name": "csv-rag-server",
  "version": "1.0.0",
  "uptime_seconds": 3600.0,
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
    "active_connections": 0,
    "connection_stats": {
      "total_connections": 5,
      "active_connections": 0,
      "connection_utilization": 0.0
    }
  }
}
```

### 2. MCP Protocol Verification

Test the MCP endpoint:

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

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "server_name": "csv-rag-server",
    "version": "1.0.0",
    "status": "running",
    "uptime_seconds": 3600.0,
    "components": {
      "csv_parser": "ok",
      "fastembed": "ok",
      "qdrant_client": "ok",
      "langgraph": "ok"
    },
    "last_health_check": "2024-01-01T12:00:00Z"
  }
}
```

## Troubleshooting Guide

### Common Connection Issues

#### 1. Connection Refused

**Symptoms:**
- `Connection refused` error
- `curl: (7) Failed to connect`

**Solutions:**
1. Verify server is running:
   ```bash
   ps aux | grep python | grep app.main
   ```

2. Check server logs for startup errors:
   ```bash
   python -m app.main
   ```

3. Verify port is not blocked:
   ```bash
   netstat -tlnp | grep 8080
   ```

4. Check firewall settings:
   ```bash
   # Linux
   sudo ufw status
   
   # macOS
   sudo pfctl -sr
   ```

#### 2. Timeout Errors

**Symptoms:**
- Request timeouts
- `curl: (28) Operation timed out`

**Solutions:**
1. Increase timeout values:
   ```bash
   export MCP_TIMEOUT=60
   ```

2. Check server performance:
   ```bash
   curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8080/health
   ```

3. Monitor server resources:
   ```bash
   top -p $(pgrep -f "app.main")
   ```

#### 3. HTTP 503 Service Unavailable

**Symptoms:**
- HTTP 503 responses
- "Service Unavailable" errors

**Solutions:**
1. Check component health:
   ```bash
   curl http://localhost:8080/health | jq '.components'
   ```

2. Verify Qdrant connection:
   ```bash
   curl http://localhost:6333/collections
   ```

3. Check server logs for component errors

#### 4. JSON-RPC Errors

**Symptoms:**
- Invalid JSON-RPC responses
- Method not found errors

**Solutions:**
1. Verify JSON-RPC format:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "tools/call",
     "params": {
       "name": "get_server_status",
       "arguments": {}
     }
   }
   ```

2. Check available tools:
   ```bash
   curl -X POST http://localhost:8080/mcp/ \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/list",
       "params": {}
     }'
   ```

#### 5. CORS Issues

**Symptoms:**
- CORS policy errors in browser
- Preflight request failures

**Solutions:**
1. Enable CORS in server configuration:
   ```bash
   export ENABLE_CORS=true
   export CORS_ORIGINS=*
   ```

2. Check CORS headers:
   ```bash
   curl -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type" \
        -X OPTIONS \
        http://localhost:8080/mcp/
   ```

### Network Configuration Issues

#### 1. Host Binding Problems

**Issue:** Server only accessible from localhost

**Solution:**
```bash
# Bind to all interfaces
export HTTP_HOST=0.0.0.0

# Or bind to specific interface
export HTTP_HOST=192.168.1.100
```

#### 2. Port Conflicts

**Issue:** Port already in use

**Solutions:**
1. Find process using port:
   ```bash
   lsof -i :8080
   ```

2. Use different port:
   ```bash
   export HTTP_PORT=8001
   ```

3. Kill conflicting process:
   ```bash
   kill -9 <PID>
   ```

#### 3. DNS Resolution Issues

**Issue:** Cannot resolve hostname

**Solutions:**
1. Use IP address instead of hostname
2. Add entry to `/etc/hosts`:
   ```
   192.168.1.100 rag-server.local
   ```

### Performance Issues

#### 1. Slow Response Times

**Diagnostics:**
```bash
# Test response time
curl -w "Total time: %{time_total}s\n" \
     -o /dev/null -s \
     http://localhost:8080/health

# Monitor server resources
htop
```

**Solutions:**
1. Increase server resources
2. Optimize Qdrant configuration
3. Reduce batch sizes
4. Enable connection pooling

#### 2. Memory Issues

**Diagnostics:**
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head

# Monitor server memory
watch -n 1 'ps -p $(pgrep -f "app.main") -o pid,ppid,cmd,%mem,%cpu'
```

**Solutions:**
1. Reduce `max_concurrent_connections`
2. Decrease `embedding_batch_size`
3. Implement request queuing
4. Add memory limits in Docker

### Authentication Issues (Future)

When authentication is implemented:

#### 1. API Key Issues

**Solutions:**
1. Verify API key format
2. Check key expiration
3. Ensure proper header format:
   ```bash
   curl -H "Authorization: Bearer your-api-key" \
        http://localhost:8080/mcp/
   ```

#### 2. Token Validation Errors

**Solutions:**
1. Check token format and encoding
2. Verify token signature
3. Ensure clock synchronization

## Advanced Configuration

### Load Balancer Setup

For production deployments with load balancers:

#### nginx Configuration

```nginx
upstream rag_mcp_servers {
    server 127.0.0.1:8080;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name rag-mcp.example.com;

    location /mcp/ {
        proxy_pass http://rag_mcp_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://rag_mcp_servers;
        proxy_set_header Host $host;
        
        # Health check specific settings
        proxy_connect_timeout 5s;
        proxy_send_timeout 5s;
        proxy_read_timeout 5s;
    }
}
```

#### HAProxy Configuration

```
global
    daemon

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend rag_mcp_frontend
    bind *:80
    default_backend rag_mcp_backend

backend rag_mcp_backend
    balance roundrobin
    option httpchk GET /health
    server rag1 127.0.0.1:8080 check
    server rag2 127.0.0.1:8001 check
    server rag3 127.0.0.1:8002 check
```

### SSL/TLS Configuration

For HTTPS support (future enhancement):

#### nginx SSL Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name rag-mcp.example.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    location /mcp/ {
        proxy_pass http://rag_mcp_servers;
        # ... other proxy settings
    }
}
```

### Monitoring and Logging

#### Prometheus Metrics (Future)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'rag-mcp-server'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

#### Log Aggregation

```yaml
# docker-compose.logging.yml
version: '3.8'
services:
  rag-mcp-server:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=rag-mcp-server"
```

## Security Considerations

### Network Security

1. **Firewall Configuration:**
   ```bash
   # Allow only specific IPs
   sudo ufw allow from 192.168.1.0/24 to any port 8080
   
   # Block all other access
   sudo ufw deny 8080
   ```

2. **VPN Access:**
   - Use VPN for remote access
   - Implement network segmentation
   - Monitor access logs

3. **Rate Limiting:**
   ```nginx
   # nginx rate limiting
   limit_req_zone $binary_remote_addr zone=mcp:10m rate=10r/s;
   
   location /mcp/ {
       limit_req zone=mcp burst=20 nodelay;
       # ... other settings
   }
   ```

### Application Security

1. **Input Validation:**
   - Server validates all MCP requests
   - Sanitize file paths for CSV ingestion
   - Limit query string lengths

2. **Resource Limits:**
   ```bash
   # Set resource limits
   export MAX_CONCURRENT_CONNECTIONS=50
   export CONNECTION_TIMEOUT=120
   export REQUEST_TIMEOUT=30
   ```

3. **Monitoring:**
   - Monitor failed authentication attempts
   - Track unusual request patterns
   - Set up alerting for errors

## Next Steps

1. **Choose your client setup method** based on your use case
2. **Configure the server** with appropriate HTTP transport settings
3. **Test the connection** using the verification steps
4. **Implement error handling** in your client code
5. **Set up monitoring** for production deployments
6. **Configure security measures** as needed

For additional examples and advanced configurations, see the [MCP Client Configuration Examples](mcp-client-configurations.md) document.