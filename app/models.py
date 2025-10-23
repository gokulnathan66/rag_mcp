from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
import uuid


class CSVDocument(BaseModel):
    """Pydantic model for CSV document representation."""
    document_id: str = Field(..., description="Unique document identifier")
    source_file: str = Field(..., description="Path to the source CSV file")
    row_number: int = Field(..., ge=1, description="Row number in the CSV file (1-indexed)")
    content: Dict[str, Any] = Field(..., description="Document content as key-value pairs from CSV columns")
    ingestion_time: datetime = Field(default_factory=datetime.utcnow, description="Document ingestion timestamp")
    document_type: Optional[str] = Field(None, description="Optional document type classification")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z" if v.tzinfo is None else v.isoformat()
        }
    
    @field_validator('document_id')
    @classmethod
    def validate_document_id(cls, v):
        if not v or not v.strip():
            raise ValueError('document_id cannot be empty')
        return v
    
    @field_validator('source_file')
    @classmethod
    def validate_source_file(cls, v):
        if not v or not v.strip():
            raise ValueError('source_file cannot be empty')
        return v


class FirestoreDocument(BaseModel):
    """Pydantic model for Firestore document representation."""
    document_id: str = Field(..., description="Unique document identifier from Firestore")
    collection_path: str = Field(..., description="Full path to the Firestore collection")
    content: Dict[str, Any] = Field(..., description="Document content as key-value pairs")
    create_time: datetime = Field(..., description="Document creation timestamp")
    update_time: datetime = Field(..., description="Document last update timestamp")
    document_type: Optional[str] = Field(None, description="Optional document type classification")
    
    @field_validator('document_id')
    @classmethod
    def validate_document_id(cls, v):
        if not v or not v.strip():
            raise ValueError('document_id cannot be empty')
        return v
    
    @field_validator('collection_path')
    @classmethod
    def validate_collection_path(cls, v):
        if not v or not v.strip():
            raise ValueError('collection_path cannot be empty')
        return v


class DocumentChunk(BaseModel):
    """Pydantic model for document chunks created during processing."""
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk identifier")
    parent_document_id: str = Field(..., description="ID of the parent Firestore document")
    content: str = Field(..., description="Text content of the chunk")
    chunk_index: int = Field(..., ge=0, description="Index of chunk within the parent document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional chunk metadata")
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError('chunk content cannot be empty')
        return v


class DocumentEmbedding(BaseModel):
    """Pydantic model for document embeddings."""
    chunk_id: str = Field(..., description="ID of the associated document chunk")
    vector: List[float] = Field(..., description="Embedding vector values")
    model_name: str = Field(..., description="Name of the embedding model used")
    embedding_type: Literal["dense", "sparse"] = Field(..., description="Type of embedding")
    
    @field_validator('vector')
    @classmethod
    def validate_vector(cls, v):
        if not v or len(v) == 0:
            raise ValueError('vector cannot be empty')
        return v


class QdrantPoint(BaseModel):
    """Pydantic model for Qdrant vector points."""
    id: str = Field(..., description="Point ID (typically chunk_id)")
    vector: Union[List[float], Dict[str, List[float]]] = Field(..., description="Vector data for similarity search")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Metadata payload for the point")
    
    @field_validator('payload')
    @classmethod
    def validate_payload(cls, v):
        # Ensure minimum required payload fields are present
        # Only require document_id and content as minimum
        if 'document_id' not in v:
            raise ValueError('payload must contain document_id')
        if 'content' not in v:
            raise ValueError('payload must contain content')
        return v


class QueryResult(BaseModel):
    """Pydantic model for query results returned to MCP clients."""
    document_id: str = Field(..., description="ID of the source document")
    chunk_id: str = Field(..., description="ID of the matching document chunk")
    content: str = Field(..., description="Text content of the matching chunk")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score between 0 and 1")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional result metadata")
    csv_metadata: CSVDocument = Field(..., description="Original CSV document metadata")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z" if v.tzinfo is None else v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Pydantic model for structured error responses."""
    error_code: str = Field(..., description="Machine-readable error code")
    error_message: str = Field(..., description="Human-readable error message")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    retry_after: Optional[int] = Field(None, ge=0, description="Seconds to wait before retrying")
    correlation_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique error correlation ID")


class ServerStatus(BaseModel):
    """Pydantic model for server status information."""
    server_name: str = Field(..., description="Name of the MCP server")
    version: str = Field(..., description="Server version")
    status: Literal["starting", "running", "stopping", "error"] = Field(..., description="Current server status")
    uptime_seconds: Optional[float] = Field(None, ge=0, description="Server uptime in seconds")
    components: Dict[str, str] = Field(default_factory=dict, description="Status of individual components")
    last_health_check: Optional[datetime] = Field(None, description="Timestamp of last health check")


class IngestionStatus(BaseModel):
    """Pydantic model for document ingestion status."""
    status: Literal["success", "partial", "failed"] = Field(..., description="Overall ingestion status")
    collection_name: str = Field(..., description="Name of the ingested collection")
    documents_processed: int = Field(..., ge=0, description="Number of documents processed")
    chunks_created: int = Field(..., ge=0, description="Number of chunks created")
    embeddings_generated: int = Field(..., ge=0, description="Number of embeddings generated")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered during ingestion")
    processing_time_seconds: Optional[float] = Field(None, ge=0, description="Total processing time")


class HTTPErrorResponse(BaseModel):
    """Pydantic model for HTTP transport error responses."""
    error_code: str = Field(..., description="Machine-readable error code")
    error_message: str = Field(..., description="Human-readable error message")
    http_status_code: int = Field(..., ge=100, le=599, description="HTTP status code")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    retry_after: Optional[int] = Field(None, ge=0, description="Seconds to wait before retrying")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique error correlation ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    transport: Literal["http"] = Field(default="http", description="Transport type")
    
    @field_validator('http_status_code')
    @classmethod
    def validate_http_status_code(cls, v):
        if not (100 <= v <= 599):
            raise ValueError('HTTP status code must be between 100 and 599')
        return v


class HTTPRequestContext(BaseModel):
    """Pydantic model for HTTP request context information."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique request identifier")
    connection_id: Optional[str] = Field(None, description="HTTP connection identifier")
    method: str = Field(..., description="HTTP request method")
    path: str = Field(..., description="HTTP request path")
    client_ip: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Request timestamp")
    
    @field_validator('method')
    @classmethod
    def validate_method(cls, v):
        valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        if v.upper() not in valid_methods:
            raise ValueError(f'Invalid HTTP method: {v}')
        return v.upper()


class HTTPResponseContext(BaseModel):
    """Pydantic model for HTTP response context information."""
    request_id: str = Field(..., description="Associated request identifier")
    status_code: int = Field(..., ge=100, le=599, description="HTTP response status code")
    response_time_ms: Optional[float] = Field(None, ge=0, description="Response time in milliseconds")
    content_length: Optional[int] = Field(None, ge=0, description="Response content length in bytes")
    error: Optional[str] = Field(None, description="Error message if response failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
