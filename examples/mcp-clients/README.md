# MCP Client Examples

This directory contains example client implementations for connecting to the RAG MCP Server using HTTP transport.

## Overview

The RAG MCP Server supports HTTP transport, allowing various types of clients to connect and use the CSV ingestion and document query capabilities. This directory provides ready-to-use examples for different programming languages and tools.

## Available Examples

### 1. Cursor IDE Configuration (`cursor-ide/`)

MCP configuration files for Cursor IDE integration:

- `mcp.json` - Basic local server configuration
- `mcp-remote.json` - Remote server configuration with error handling

**Usage:**
1. Copy the appropriate configuration to your Cursor IDE MCP settings
2. Ensure Python and requests are installed
3. Start the RAG MCP Server with HTTP transport enabled
4. Restart Cursor IDE to load the new configuration

### 2. Python Client (`python/`)

Simple Python client with interactive CLI:

- `simple_client.py` - Full-featured Python MCP client

**Features:**
- Connection testing
- Interactive command-line interface
- All MCP tool support (status, health, ingest, query)
- Error handling and retry logic

**Usage:**
```bash
# Install dependencies
pip install requests

# Run interactive mode
python simple_client.py

# Run specific commands
python simple_client.py http://localhost:8000 test
python simple_client.py http://localhost:8000 status
```

### 3. Node.js Client (`nodejs/`)

Node.js client with both CLI and programmatic interfaces:

- `simple-client.js` - Node.js MCP client
- `package.json` - NPM package configuration

**Features:**
- Async/await support
- Interactive and command-line modes
- Full MCP protocol support
- Error handling and timeouts

**Usage:**
```bash
# Install dependencies
cd nodejs/
npm install

# Run interactive mode
npm start

# Run specific commands
node simple-client.js test
node simple-client.js query "What products are available?"
```

### 4. curl Client (`curl/`)

Shell script for curl-based testing and automation:

- `test-client.sh` - Comprehensive curl-based client

**Features:**
- Interactive and command-line modes
- Colored output and logging
- Health checks and connection testing
- JSON response formatting with jq

**Usage:**
```bash
# Make executable
chmod +x test-client.sh

# Run connection test
./test-client.sh test

# Interactive mode
./test-client.sh interactive

# Specific commands
./test-client.sh status
./test-client.sh query "What products are available?" 5 0.7
```

## Quick Start

### 1. Start the RAG MCP Server

Ensure the server is running with HTTP transport:

```bash
# Set environment variables
export TRANSPORT_MODE=http
export HTTP_HOST=0.0.0.0
export HTTP_PORT=8000

# Start server
python -m app.main
```

### 2. Test Connection

Use any client to test the connection:

```bash
# Python client
python examples/mcp-clients/python/simple_client.py

# Node.js client
node examples/mcp-clients/nodejs/simple-client.js test

# curl client
./examples/mcp-clients/curl/test-client.sh test

# Direct curl
curl http://localhost:8000/health
```

### 3. Try the Tools

#### Get Server Status
```bash
# Python
python simple_client.py
# In interactive mode: status

# Node.js
node simple-client.js status

# curl
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

#### Ingest CSV File
```bash
# Python
python simple_client.py
# In interactive mode: ingest ./data/sample_products.csv

# Node.js
node simple-client.js ingest ./data/sample_products.csv

# curl
./test-client.sh ingest ./data/sample_products.csv
```

#### Query Documents
```bash
# Python
python simple_client.py
# In interactive mode: query What products are available?

# Node.js
node simple-client.js query "What products are available?" 5 0.7

# curl
./test-client.sh query "What products are available?" 5 0.7
```

## Configuration

### Environment Variables

All clients support these environment variables:

```bash
# Server connection
export MCP_SERVER_URL="http://localhost:8000/mcp/"
export MCP_HEALTH_URL="http://localhost:8000/health"

# Request settings
export MCP_TIMEOUT="30"
export MCP_MAX_RETRIES="3"
export MCP_RETRY_DELAY="1"

# Debugging
export VERBOSE="true"
```

### Remote Server Connection

To connect to a remote server:

```bash
# Python
python simple_client.py http://remote-server:8000

# Node.js
node simple-client.js http://remote-server:8000 test

# curl
MCP_SERVER_URL=http://remote-server:8000/mcp/ ./test-client.sh test
```

## Client Comparison

| Feature | Python | Node.js | curl | Cursor IDE |
|---------|--------|---------|------|------------|
| Interactive Mode | ✓ | ✓ | ✓ | ✓ |
| Command Line | ✓ | ✓ | ✓ | - |
| Error Handling | ✓ | ✓ | ✓ | Basic |
| Retry Logic | ✓ | ✓ | Manual | - |
| JSON Formatting | ✓ | ✓ | ✓ (jq) | ✓ |
| Dependencies | requests | axios | curl, jq | Python |
| Platform | Cross-platform | Cross-platform | Unix/Linux | Cross-platform |

## Troubleshooting

### Common Issues

#### 1. Connection Refused
```bash
# Check if server is running
curl http://localhost:8000/health

# Check server logs
python -m app.main

# Verify port
netstat -tlnp | grep 8000
```

#### 2. Module Not Found (Python)
```bash
# Install requests
pip install requests

# Or use virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
pip install requests
```

#### 3. Package Not Found (Node.js)
```bash
# Install axios
npm install axios

# Or install globally
npm install -g axios
```

#### 4. Command Not Found (curl)
```bash
# Install curl (Ubuntu/Debian)
sudo apt-get install curl jq

# Install curl (macOS)
brew install curl jq

# Install curl (CentOS/RHEL)
sudo yum install curl jq
```

### Debug Mode

Enable verbose output for debugging:

```bash
# Python
VERBOSE=true python simple_client.py test

# Node.js
DEBUG=true node simple-client.js test

# curl
VERBOSE=true ./test-client.sh test
```

### Network Issues

Test network connectivity:

```bash
# Test basic connectivity
ping localhost

# Test port accessibility
telnet localhost 8000

# Test HTTP response
curl -v http://localhost:8000/health
```

## Development

### Adding New Clients

To add a new client implementation:

1. Create a new directory: `examples/mcp-clients/your-language/`
2. Implement the MCP JSON-RPC protocol over HTTP
3. Support these core methods:
   - `tools/call` with `get_server_status`
   - `tools/call` with `ingest_csv`
   - `tools/call` with `query_documents`
4. Add health check support via GET `/health`
5. Include error handling and timeouts
6. Add documentation and examples

### Testing New Clients

Use the test server for development:

```bash
# Start test server
python -m app.main

# Test your client
your-client test
your-client status
your-client health
```

## Security Considerations

### Network Security

- Use HTTPS in production (when available)
- Implement proper authentication (when available)
- Validate all inputs
- Use secure network configurations

### Client Security

- Validate server responses
- Implement request timeouts
- Use secure HTTP libraries
- Handle errors gracefully

### Example Secure Configuration

```bash
# Use HTTPS (when available)
export MCP_SERVER_URL="https://secure-server:8443/mcp/"

# Set reasonable timeouts
export MCP_TIMEOUT="30"
export MCP_MAX_RETRIES="3"

# Enable certificate validation
export MCP_VERIFY_SSL="true"
```

## Contributing

To contribute new client examples:

1. Follow the existing directory structure
2. Include comprehensive error handling
3. Add interactive and command-line modes
4. Include documentation and usage examples
5. Test with the RAG MCP Server
6. Submit a pull request

## License

These examples are provided under the same license as the RAG MCP Server project.