from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


class FirestoreDocument(BaseModel):
    document_id: str
    collection_path: str
    content: Dict[str, Any]
    create_time: datetime
    update_time: datetime
    document_type: Optional[str]


class DocumentChunk(BaseModel):
    chunk_id: str
    parent_document_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any]


class DocumentEmbedding(BaseModel):
    chunk_id: str
    vector: List[float]
    model_name: str
    embedding_type: Literal["dense", "sparse"]


class QueryResult(BaseModel):
    document_id: str
    chunk_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any]
    firestore_metadata: FirestoreDocument


class ErrorResponse(BaseModel):
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None
    correlation_id: Optional[str] = None
