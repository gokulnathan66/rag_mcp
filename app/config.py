from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings
from typing import Dict, Optional


class ServerConfig(BaseSettings):
    """Server configuration with environment variable support."""
    
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
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
