# Container Deployment Guide

This guide covers deploying the RAG MCP Server in containerized environments with proper health checks and lifecycle management.

## Docker Deployment

### Basic Docker Run

```bash
# Default transport (stdio) mode
docker run -d \
  --name rag-mcp-server \
  -v $(pwd)/data:/app/data:ro \
  -e QDRANT_URL=http://host.docker.internal:6333 \
  rag-mcp-server:latest

# HTTP transport mode
docker run -d \
  --name rag-mcp-server \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data:ro \
  -e TRANSPORT_MODE=http \
  -e HTTP_HOST=0.0.0.0 \
  -e HTTP_PORT=8000 \
  -e QDRANT_URL=http://host.docker.internal:6333 \
  rag-mcp-server:latest
```

### Docker Compose Deployment

#### Default Mode
```bash
# Start with default transport (stdio)
docker-compose up -d
```

#### HTTP Transport Mode
```bash
# Start with HTTP transport enabled
docker-compose -f docker-compose.yml -f docker-compose.http.yml up -d
```

#### Environment Configuration
Create a `.env` file with your configuration:

```env
# Transport Configuration
TRANSPORT_MODE=http
HTTP_HOST=0.0.0.0
HTTP_PORT=8000
MAX_CONCURRENT_CONNECTIONS=100
CONNECTION_TIMEOUT=300
REQUEST_TIMEOUT=60
ENABLE_CORS=true
CORS_ORIGINS=*
ENABLE_HEALTH_ENDPOINT=true
HEALTH_CHECK_PATH=/health

# Application Configuration
MCP_SERVER_NAME=csv-rag-server
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=csv_documents
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
LOG_LEVEL=INFO
```

## Health Checks

The container includes comprehensive health checks that work with both transport modes:

### HTTP Transport Health Check
- **Endpoint**: `GET /health`
- **Expected Response**: JSON with status information
- **Timeout**: 10 seconds
- **Interval**: 30 seconds

### Default Transport Health Check
- **Method**: Python module import test
- **Validates**: Application can start and import required modules
- **Timeout**: 10 seconds

### Health Check Script
The container uses `docker-healthcheck.py` which automatically detects the transport mode and performs appropriate health checks.

## Container Lifecycle Management

### Graceful Shutdown
The application handles the following signals for graceful shutdown:
- `SIGTERM`: Standard container stop signal
- `SIGINT`: Interrupt signal (Ctrl+C)

### Shutdown Sequence
1. Signal handler catches shutdown signal
2. HTTP connections are gracefully closed (if HTTP transport)
3. Qdrant connections are closed
4. Thread pools and async tasks are shutdown
5. Resources are cleaned up
6. Process exits cleanly

### Timeout Configuration
- **Default shutdown timeout**: 25 seconds
- **Container termination grace period**: 30 seconds
- **Health check timeout**: 10 seconds

## Kubernetes Deployment

### Basic Deployment
```bash
# Apply the Kubernetes manifests
kubectl apply -f k8s-deployment.yml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get services
```

### Scaling
```bash
# Manual scaling
kubectl scale deployment rag-mcp-server --replicas=5

# Auto-scaling is configured via HorizontalPodAutoscaler
kubectl get hpa
```

### Health Monitoring
```bash
# Check pod health
kubectl describe pod <pod-name>

# View health check logs
kubectl logs <pod-name>

# Test health endpoint
kubectl port-forward service/rag-mcp-service 8080:80
curl http://localhost:8080/health
```

## Load Balancer Integration

### Traefik Configuration
The `docker-compose.http.yml` includes Traefik labels for automatic service discovery:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.rag-mcp.rule=Host(`rag-mcp.localhost`)"
  - "traefik.http.services.rag-mcp.loadbalancer.server.port=8000"
```

### NGINX Configuration
Example NGINX upstream configuration:

```nginx
upstream rag_mcp_backend {
    server rag-mcp-server-1:8000 max_fails=3 fail_timeout=30s;
    server rag-mcp-server-2:8000 max_fails=3 fail_timeout=30s;
    server rag-mcp-server-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name rag-mcp.example.com;
    
    location /health {
        proxy_pass http://rag_mcp_backend/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /mcp/ {
        proxy_pass http://rag_mcp_backend/mcp/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring and Logging

### Container Logs
```bash
# Docker logs
docker logs rag-mcp-server -f

# Docker Compose logs
docker-compose logs -f rag-mcp-server

# Kubernetes logs
kubectl logs -f deployment/rag-mcp-server
```

### Health Check Monitoring
```bash
# Check container health status
docker inspect rag-mcp-server | jq '.[0].State.Health'

# Monitor health check logs
docker logs rag-mcp-server 2>&1 | grep -i health
```

### Metrics Collection
The application integrates with Pydantic Logfire for metrics collection. Configure the following environment variables:

```env
ENABLE_LOGFIRE=true
LOG_LEVEL=INFO
```

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Check what's using the port
lsof -i :8000
netstat -tulpn | grep :8000

# Change the port
export HTTP_PORT=8001
docker-compose up -d
```

#### Health Check Failures
```bash
# Check health check logs
docker logs rag-mcp-server 2>&1 | grep -i health

# Manual health check
docker exec rag-mcp-server python docker-healthcheck.py

# Test HTTP health endpoint
curl -f http://localhost:8000/health
```

#### Container Won't Start
```bash
# Check container logs
docker logs rag-mcp-server

# Check configuration
docker exec rag-mcp-server env | grep -E "(TRANSPORT|HTTP|QDRANT)"

# Validate configuration
docker exec rag-mcp-server python -c "from app.config import ServerConfig; print(ServerConfig())"
```

#### Graceful Shutdown Issues
```bash
# Check if signals are being handled
docker logs rag-mcp-server 2>&1 | grep -i "signal\|shutdown"

# Test graceful shutdown
docker stop rag-mcp-server  # Should complete within 30 seconds
```

### Performance Tuning

#### Resource Limits
```yaml
# Docker Compose
services:
  rag-mcp-server:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.25'
```

#### Connection Limits
```env
MAX_CONCURRENT_CONNECTIONS=200
CONNECTION_TIMEOUT=600
REQUEST_TIMEOUT=120
```

#### Health Check Tuning
```yaml
healthcheck:
  interval: 15s      # More frequent checks
  timeout: 5s        # Faster timeout
  retries: 5         # More retries
  start_period: 60s  # Longer startup time
```

## Security Considerations

### Container Security
- Run as non-root user (UID 1000)
- Read-only data volumes
- Minimal base image (python:3.11-slim)
- No unnecessary packages

### Network Security
- Bind to specific interfaces when needed
- Use CORS configuration for web clients
- Implement proper authentication (future enhancement)

### Secrets Management
```bash
# Use Docker secrets for sensitive data
echo "your-api-key" | docker secret create qdrant-api-key -

# Mount secrets in container
docker service create \
  --name rag-mcp-server \
  --secret qdrant-api-key \
  rag-mcp-server:latest
```