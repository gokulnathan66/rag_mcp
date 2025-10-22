from pydantic import BaseModel, Field, ConfigDict, validator
from pydantic_settings import BaseSettings
from typing import Dict, Optional, List, Literal
import ipaddress


class HTTPTransportConfig(BaseModel):
    """HTTP transport configuration for MCP server."""
    
    # HTTP Server Configuration
    enable_http_transport: bool = Field(default=False, description="Enable HTTP transport mode")
    http_host: str = Field(default="127.0.0.1", description="HTTP server host address")
    http_port: int = Field(default=8000, ge=1024, le=65535, description="HTTP server port")
    
    # Connection Management
    max_concurrent_connections: int = Field(default=100, ge=1, description="Maximum concurrent HTTP connections")
    connection_timeout: int = Field(default=300, ge=1, description="HTTP connection timeout in seconds")
    request_timeout: int = Field(default=60, ge=1, description="HTTP request timeout in seconds")
    
    # CORS Configuration
    enable_cors: bool = Field(default=True, description="Enable CORS for web clients")
    cors_origins: List[str] = Field(default=["*"], description="Allowed CORS origins")
    cors_methods: List[str] = Field(default=["GET", "POST", "OPTIONS"], description="Allowed CORS methods")
    cors_headers: List[str] = Field(default=["*"], description="Allowed CORS headers")
    
    # Health Check Configuration
    enable_health_endpoint: bool = Field(default=True, description="Enable /health endpoint")
    health_check_path: str = Field(default="/health", description="Health check endpoint path")
    
    @validator('http_host')
    def validate_host(cls, v):
        """Validate HTTP host address."""
        if v in ['localhost', '0.0.0.0']:
            return v
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")
    
    @validator('health_check_path')
    def validate_health_path(cls, v):
        """Validate health check path format."""
        if not v.startswith('/'):
            raise ValueError("Health check path must start with '/'")
        return v
    
    @validator('cors_origins')
    def validate_cors_origins(cls, v):
        """Validate CORS origins format."""
        if not v:
            raise ValueError("CORS origins cannot be empty")
        return v


class ServerConfig(BaseSettings):
    """Server configuration with environment variable support."""
    
    # Transport Mode Configuration
    transport_mode: Literal["default", "http"] = Field(
        default="default", 
        description="MCP transport mode (default=stdio, http=HTTP transport)"
    )
    
    # FastMCP Configuration
    mcp_server_name: str = Field(default="csv-rag-server", description="MCP server name")
    mcp_version: str = Field(default="1.0.0", description="MCP server version")
    
    # CSV Configuration
    csv_data_directory: str = Field(default="./data", description="Directory containing CSV files")
    csv_delimiter: str = Field(default=",", description="CSV delimiter character")
    csv_encoding: str = Field(default="utf-8", description="CSV file encoding")
    csv_column_mapping: Optional[Dict[str, str]] = Field(default=None, description="Optional column name mapping")
    
    # Firestore Configuration
    firestore_project_id: Optional[str] = Field(default=None, description="Google Cloud Firestore project ID")
    firestore_credentials_path: Optional[str] = Field(default=None, description="Path to Firestore service account credentials")
    firestore_database_id: str = Field(default="(default)", description="Firestore database ID")
    
    # Qdrant Configuration
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant API key for authentication")
    qdrant_collection_name: str = Field(default="firestore_documents", description="Qdrant collection name for storing vectors")
    
    # FastEmbed Configuration
    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="FastEmbed model name")
    embedding_batch_size: int = Field(default=32, description="Batch size for embedding generation")
    enable_sparse_embeddings: bool = Field(default=False, description="Enable sparse embeddings for hybrid search")
    
    # Processing Configuration
    max_chunk_size: int = Field(default=1000, description="Maximum size of document chunks")
    chunk_overlap: int = Field(default=200, description="Overlap between document chunks")
    max_concurrent_requests: int = Field(default=10, description="Maximum concurrent requests")
    
    # Monitoring Configuration
    enable_logfire: bool = Field(default=True, description="Enable Pydantic Logfire monitoring")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # HTTP Transport Configuration
    http_transport: HTTPTransportConfig = Field(
        default_factory=HTTPTransportConfig,
        description="HTTP transport configuration"
    )
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__"
    )
    
    @validator('transport_mode')
    def validate_transport_mode(cls, v, values):
        """Validate transport mode configuration."""
        return v
    
    def get_transport_config(self) -> Dict[str, any]:
        """Get transport-specific configuration."""
        if self.transport_mode == "http":
            return {
                "transport": "http",
                "host": self.http_transport.http_host,
                "port": self.http_transport.http_port,
                "timeout": self.http_transport.connection_timeout
            }
        else:
            return {"transport": "stdio"}
    
    def validate_http_transport_config(self) -> List[str]:
        """Validate HTTP transport configuration and return any errors."""
        errors = []
        
        if self.transport_mode == "http":
            # Validate that HTTP transport is enabled when mode is http
            if not self.http_transport.enable_http_transport:
                errors.append("HTTP transport must be enabled when transport_mode is 'http'")
            
            # Validate port availability (basic check)
            if self.http_transport.http_port < 1024:
                errors.append("HTTP port should be >= 1024 for non-privileged operation")
            
            # Validate timeout values are reasonable
            if self.http_transport.connection_timeout > 3600:
                errors.append("Connection timeout should not exceed 1 hour (3600 seconds)")
            
            if self.http_transport.request_timeout > self.http_transport.connection_timeout:
                errors.append("Request timeout cannot exceed connection timeout")
            
            # Validate connection limits
            if self.http_transport.max_concurrent_connections > 1000:
                errors.append("Maximum concurrent connections should not exceed 1000 for stability")
        
        return errors
