from pydantic import BaseModel
from typing import Optional


class ServerConfig(BaseModel):
    mcp_server_name: str = "firestore-rag-server"
    mcp_version: str = "1.0.0"
    firestore_project_id: Optional[str] = None
    firestore_credentials_path: Optional[str] = None
    firestore_database_id: str = "(default)"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "firestore_documents"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    enable_sparse_embeddings: bool = False
    max_chunk_size: int = 1000
    chunk_overlap: int = 200
    max_concurrent_requests: int = 10
    enable_logfire: bool = True
    log_level: str = "INFO"
