# RAG MCP Server

This repository contains the RAG (Retrieval-Augmented Generation) MCP Server: a FastMCP-based service that exposes document retrieval tools over the Model Context Protocol. The system ingests documents from Google Firestore, generates embeddings with FastEmbed (ONNX runtime), and performs similarity search using Qdrant.

## Contents

- Design overview and architecture
- Requirements and acceptance criteria
- Data models and error-handling strategy
- Deployment notes (Docker Compose)

This README consolidates the design and requirements documents located in `.kiro/specs/rag-mcp-server/`.

## Overview

The RAG MCP Server is a production-ready retrieval-augmented generation system that integrates Google Firestore as the document source with Qdrant vector database for similarity search. Built using the FastMCP framework, the system provides real-time document synchronization and high-performance query capabilities through the Model Context Protocol.

### High-level architecture

Components:

- MCP Client -> FastMCP Server
- FastMCP Server -> LangGraph orchestrator
- LangGraph -> Firestore client, FastEmbed, Qdrant client
- Firestore stores documents; Qdrant stores vectors
- FastEmbed uses ONNX runtime for embedding generation

Cross-cutting concerns: Pydantic validation and Logfire monitoring.

## Component Responsibilities

1. FastMCP Server
	 - Handles MCP (JSON-RPC 2.0) communication and exposes RAG tools.
	 - Example tool interfaces:

```python
@mcp.tool
async def query_documents(query: str, max_results: int = 10) -> List[DocumentResult]

@mcp.tool
async def ingest_firestore_collection(collection_name: str, filters: Optional[Dict] = None) -> IngestionResult

@mcp.tool
async def get_server_status() -> ServerStatus
```

2. LangGraph Orchestrator
	 - Coordinates multi-step RAG workflows (query parsing, extraction, chunking, embedding, storage, search, assembly).
	 - Manages state, retries, and concurrent operations.

3. Firestore Integration
	 - Connects to Google Firestore using service account credentials.
	 - Supports async operations, collection-group queries, and real-time listeners for synchronization.

4. FastEmbed Processing
	 - Generates embeddings using ONNX-optimized models (default: `sentence-transformers/all-MiniLM-L6-v2`).
	 - Supports batching and optional sparse models.

5. Qdrant Vector Database
	 - Stores indexed vectors and payload metadata, supports hybrid search and persistent storage.

## Data Models (Pydantic)

Key models:

- FirestoreDocument: document_id, collection_path, content, create_time, update_time, document_type
- DocumentChunk: chunk_id, parent_document_id, content, chunk_index, metadata
- DocumentEmbedding: chunk_id, vector, model_name, embedding_type
- QueryResult: document_id, chunk_id, content, similarity_score, metadata, firestore_metadata

QdrantPoint payload includes document_id, collection_path, content, chunk_index, create_time, update_time, and embedding_model.

## Error Handling

Categories and strategies:

- Connection errors: retries with exponential backoff, circuit breaker for Qdrant
- Processing errors: fallback models, skip invalid docs, retries
- Validation errors: Pydantic validation and structured error responses
- Resource errors: batch-size reduction, alerting on disk/memory issues

Error response shape:

```python
class ErrorResponse(BaseModel):
		error_code: str
		error_message: str
		error_details: Optional[Dict[str, Any]]
		retry_after: Optional[int]
		correlation_id: str
```

## Requirements (summary)

The server must support:

- Natural language query -> query embedding -> similarity search in Qdrant -> return ranked documents with similarity scores and Firestore metadata (configurable result limit).
- Ingesting Firestore collections: extract documents, chunk large documents, generate embeddings, store vectors and payloads in Qdrant.
- MCP protocol support: expose retrieval as MCP tools and return valid MCP responses.
- Configuration: FastEmbed model selection, Qdrant connection, Firestore credentials/filters, LangGraph chunking strategies.
- Real-time sync: detect Firestore create/update/delete via listeners and keep Qdrant in sync.
- Graceful error handling and monitoring via Pydantic/Logfire.

Acceptance criteria are fully listed in `.kiro/specs/rag-mcp-server/requirements.md` and should be used when implementing tests and CI checks.

## Testing Strategy

- Unit tests for MCP tools, LangGraph nodes, Firestore client, embedding generation, and Qdrant operations.
- Integration tests with Firestore emulator and a containerized Qdrant test instance.
- End-to-end tests for ingestion and query pipelines, including real-time sync and error scenarios.

## Deployment

Example Docker Compose (see `.kiro/specs/rag-mcp-server/design.md`):

```yaml
version: '3.8'
services:
	qdrant:
		image: qdrant/qdrant:latest
		ports:
			- "6333:6333"
			- "6334:6334"
		volumes:
			- ./qdrant_storage:/qdrant/storage

	rag-mcp-server:
		build: .
		ports:
			- "8000:8000"
		environment:
			- FIRESTORE_PROJECT_ID=${FIRESTORE_PROJECT_ID}
			- FIRESTORE_CREDENTIALS_PATH=/app/credentials.json
			- QDRANT_URL=http://qdrant:6333
		volumes:
			- ./credentials.json:/app/credentials.json:ro
		depends_on:
			- qdrant
```

## Configuration

Example configuration model:

```python
class ServerConfig(BaseModel):
		mcp_server_name: str = "rag-server"
		mcp_version: str = "1.0.0"
		firestore_project_id: str
		firestore_credentials_path: str
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
```

## Real-time synchronization

Firestore listeners should implement callbacks for created, updated, and deleted documents. Sync state should be tracked in Qdrant payload metadata and use last-write-wins for conflict resolution.

## Next steps and suggestions

- Implement skeleton FastMCP server with tools `query_documents`, `ingest_firestore_collection`, and `get_server_status`.
- Add tests and a minimal docker-compose-based local dev setup (Firestore emulator + Qdrant).
- Add CI checks to run unit and integration tests using emulators/containers.

## Files

- `.kiro/specs/rag-mcp-server/design.md` — design document (source)
- `.kiro/specs/rag-mcp-server/requirements.md` — requirements and acceptance criteria (source)

## License

Add your preferred license.

---

Updated README: combined design + requirements for easier onboarding and implementation.