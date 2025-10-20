"""
RAG MCP Server - A FastMCP-based server for Retrieval-Augmented Generation.

This package provides a Model Context Protocol (MCP) server that integrates
Google Firestore as a document source with Qdrant vector database for 
similarity search capabilities.
"""

from .config import ServerConfig
from .models import (
    CSVDocument,
    FirestoreDocument,
    DocumentChunk,
    DocumentEmbedding,
    QdrantPoint,
    QueryResult,
    ErrorResponse,
    ServerStatus,
    IngestionStatus
)

__version__ = "1.0.0"
__author__ = "RAG MCP Server Team"

__all__ = [
    "ServerConfig",
    "CSVDocument",
    "FirestoreDocument", 
    "DocumentChunk",
    "DocumentEmbedding",
    "QdrantPoint",
    "QueryResult",
    "ErrorResponse",
    "ServerStatus",
    "IngestionStatus"
]