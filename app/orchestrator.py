"""
LangGraph Orchestration Workflows

This module implements LangGraph-based workflows for:
1. CSV ingestion: CSV -> Parse -> Chunk -> Embed -> Store in Qdrant
2. Query processing: Query -> Embed -> Search -> Assemble Results

Each workflow is implemented as a LangGraph StateGraph with nodes for each processing step.
"""

import logging
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from datetime import datetime
import operator

import logfire
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.config import ServerConfig
from app.csv_parser import CSVParser
from app.embedder import Embedder
from app.qdrant_client import QdrantClient
from app.models import (
    CSVDocument,
    DocumentChunk,
    DocumentEmbedding,
    QueryResult,
    IngestionStatus
)
from app.errors import FileAccessError, CSVParsingError


logger = logging.getLogger(__name__)


# ============================================================================
# State Definitions for LangGraph Workflows
# ============================================================================

class IngestionState(TypedDict):
    """State for CSV ingestion workflow."""
    # Input
    file_path: str
    
    # Processing state
    documents: List[CSVDocument]
    chunks: List[DocumentChunk]
    embeddings: List[DocumentEmbedding]
    
    # Output/Status
    status: str
    documents_processed: int
    chunks_created: int
    embeddings_generated: int
    errors: Annotated[List[str], operator.add]  # Accumulate errors
    processing_time_seconds: Optional[float]


class QueryState(TypedDict):
    """State for query processing workflow."""
    # Input
    query: str
    max_results: int
    score_threshold: Optional[float]
    
    # Processing state
    query_embedding: List[float]
    search_results: List[Dict[str, Any]]
    
    # Output
    results: List[QueryResult]
    errors: Annotated[List[str], operator.add]  # Accumulate errors


# ============================================================================
# CSV Ingestion Workflow Nodes
# ============================================================================

class CSVIngestionWorkflow:
    """
    LangGraph workflow for CSV ingestion.
    
    Workflow steps:
    1. Parse CSV file into documents
    2. Chunk documents into smaller segments
    3. Generate embeddings for chunks
    4. Store vectors in Qdrant
    """
    
    def __init__(
        self,
        csv_parser: CSVParser,
        embedder: Embedder,
        qdrant_client: QdrantClient
    ):
        """
        Initialize CSV ingestion workflow with required components.
        
        Args:
            csv_parser: CSV parser component
            embedder: FastEmbed embedder component
            qdrant_client: Qdrant vector database client
        """
        self.csv_parser = csv_parser
        self.embedder = embedder
        self.qdrant_client = qdrant_client
        
        # Build the workflow graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for CSV ingestion."""
        workflow = StateGraph(IngestionState)
        
        # Add nodes for each processing step
        workflow.add_node("parse_csv", self._parse_csv_node)
        workflow.add_node("chunk_documents", self._chunk_documents_node)
        workflow.add_node("generate_embeddings", self._generate_embeddings_node)
        workflow.add_node("store_vectors", self._store_vectors_node)
        
        # Define the workflow edges
        workflow.set_entry_point("parse_csv")
        workflow.add_edge("parse_csv", "chunk_documents")
        workflow.add_edge("chunk_documents", "generate_embeddings")
        workflow.add_edge("generate_embeddings", "store_vectors")
        workflow.add_edge("store_vectors", END)
        
        # Compile the graph with checkpointing for error recovery
        return workflow.compile(checkpointer=MemorySaver())
    
    async def _parse_csv_node(self, state: IngestionState) -> IngestionState:
        """
        Node 1: Parse CSV file into structured documents.
        
        Handles:
        - File reading with error handling
        - CSV parsing with validation
        - Document ID generation
        """
        logger.info(f"Parsing CSV file: {state['file_path']}")
        
        try:
            # Parse CSV file into documents
            documents = self.csv_parser.parse_csv_to_documents(state['file_path'])
            
            logger.info(f"Successfully parsed {len(documents)} documents from CSV")
            
            return {
                **state,
                "documents": documents,
                "documents_processed": len(documents),
                "status": "parsing_complete"
            }
            
        except (FileAccessError, CSVParsingError) as e:
            logger.error(f"CSV parsing failed: {str(e)}")
            return {
                **state,
                "documents": [],
                "documents_processed": 0,
                "status": "parsing_failed",
                "errors": [f"CSV parsing error: {str(e)}"]
            }
        except Exception as e:
            logger.error(f"Unexpected error during CSV parsing: {str(e)}")
            return {
                **state,
                "documents": [],
                "documents_processed": 0,
                "status": "parsing_failed",
                "errors": [f"Unexpected parsing error: {str(e)}"]
            }
    
    async def _chunk_documents_node(self, state: IngestionState) -> IngestionState:
        """
        Node 2: Chunk documents into smaller segments.
        
        Handles:
        - Text extraction from document content
        - Chunking with overlap
        - Metadata preservation
        """
        logger.info(f"Chunking {len(state['documents'])} documents")
        
        # Check if parsing was successful
        if state.get("status") == "parsing_failed" or not state.get("documents"):
            logger.warning("Skipping chunking due to parsing failure")
            return {
                **state,
                "chunks": [],
                "chunks_created": 0,
                "status": "chunking_skipped"
            }
        
        try:
            all_chunks = []
            
            for document in state["documents"]:
                # Convert document content to text for chunking
                # Concatenate all field values with field names
                text_parts = []
                for key, value in document.content.items():
                    text_parts.append(f"{key}: {value}")
                
                document_text = "\n".join(text_parts)
                
                # Create metadata for chunks
                chunk_metadata = {
                    "source_file": document.source_file,
                    "row_number": document.row_number,
                    "ingestion_time": document.ingestion_time.isoformat()
                }
                
                # Chunk the document text
                chunks = self.embedder.chunk_text(
                    text=document_text,
                    parent_document_id=document.document_id,
                    metadata=chunk_metadata
                )
                
                all_chunks.extend(chunks)
            
            logger.info(f"Created {len(all_chunks)} chunks from documents")
            
            return {
                **state,
                "chunks": all_chunks,
                "chunks_created": len(all_chunks),
                "status": "chunking_complete"
            }
            
        except Exception as e:
            logger.error(f"Error during document chunking: {str(e)}")
            return {
                **state,
                "chunks": [],
                "chunks_created": 0,
                "status": "chunking_failed",
                "errors": [f"Chunking error: {str(e)}"]
            }
    
    async def _generate_embeddings_node(self, state: IngestionState) -> IngestionState:
        """
        Node 3: Generate embeddings for document chunks.
        
        Handles:
        - Batch embedding generation
        - FastEmbed model usage
        - Error handling for embedding failures
        """
        logger.info(f"Generating embeddings for {len(state['chunks'])} chunks")
        
        # Check if chunking was successful
        if state.get("status") in ["parsing_failed", "chunking_failed", "chunking_skipped"] or not state.get("chunks"):
            logger.warning("Skipping embedding generation due to previous failure")
            return {
                **state,
                "embeddings": [],
                "embeddings_generated": 0,
                "status": "embedding_skipped"
            }
        
        try:
            # Generate embeddings for all chunks
            embeddings = await self.embedder.embed_documents(state["chunks"])
            
            logger.info(f"Generated {len(embeddings)} embeddings")
            
            return {
                **state,
                "embeddings": embeddings,
                "embeddings_generated": len(embeddings),
                "status": "embedding_complete"
            }
            
        except Exception as e:
            logger.error(f"Error during embedding generation: {str(e)}")
            return {
                **state,
                "embeddings": [],
                "embeddings_generated": 0,
                "status": "embedding_failed",
                "errors": [f"Embedding generation error: {str(e)}"]
            }
    
    async def _store_vectors_node(self, state: IngestionState) -> IngestionState:
        """
        Node 4: Store vectors in Qdrant database.
        
        Handles:
        - Batch upsert operations
        - Duplicate handling (updates existing vectors)
        - Connection error handling
        """
        logger.info(f"Storing {len(state['embeddings'])} vectors in Qdrant")
        
        # Check if embedding generation was successful
        if state.get("status") in ["parsing_failed", "chunking_failed", "embedding_failed", "embedding_skipped"] or not state.get("embeddings"):
            logger.warning("Skipping vector storage due to previous failure")
            return {
                **state,
                "status": "storage_skipped"
            }
        
        try:
            # Store embeddings in Qdrant
            result = await self.qdrant_client.upsert_embeddings(
                chunks=state["chunks"],
                embeddings=state["embeddings"]
            )
            
            logger.info(f"Successfully stored {result['count']} vectors in Qdrant")
            
            return {
                **state,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error storing vectors in Qdrant: {str(e)}")
            return {
                **state,
                "status": "storage_failed",
                "errors": [f"Vector storage error: {str(e)}"]
            }
    
    async def run(self, file_path: str) -> IngestionStatus:
        """
        Execute the CSV ingestion workflow.
        
        Args:
            file_path: Path to the CSV file to ingest
            
        Returns:
            IngestionStatus with results and any errors
        """
        start_time = datetime.utcnow()
        
        # Initialize state
        initial_state: IngestionState = {
            "file_path": file_path,
            "documents": [],
            "chunks": [],
            "embeddings": [],
            "status": "starting",
            "documents_processed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "errors": [],
            "processing_time_seconds": None
        }
        
        try:
            # Run the workflow
            config = {"configurable": {"thread_id": f"ingestion_{file_path}"}}
            final_state = await self.graph.ainvoke(initial_state, config)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Determine overall status
            if final_state["status"] == "success":
                overall_status = "success"
            elif final_state.get("errors"):
                overall_status = "failed"
            else:
                overall_status = "partial"
            
            return IngestionStatus(
                status=overall_status,
                collection_name=file_path,
                documents_processed=final_state["documents_processed"],
                chunks_created=final_state["chunks_created"],
                embeddings_generated=final_state["embeddings_generated"],
                errors=final_state.get("errors", []),
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return IngestionStatus(
                status="failed",
                collection_name=file_path,
                documents_processed=0,
                chunks_created=0,
                embeddings_generated=0,
                errors=[f"Workflow execution error: {str(e)}"],
                processing_time_seconds=processing_time
            )


# ============================================================================
# Query Processing Workflow Nodes
# ============================================================================

class QueryProcessingWorkflow:
    """
    LangGraph workflow for query processing.
    
    Workflow steps:
    1. Generate query embedding
    2. Perform similarity search in Qdrant
    3. Assemble and format results
    """
    
    def __init__(
        self,
        embedder: Embedder,
        qdrant_client: QdrantClient
    ):
        """
        Initialize query processing workflow with required components.
        
        Args:
            embedder: FastEmbed embedder component
            qdrant_client: Qdrant vector database client
        """
        self.embedder = embedder
        self.qdrant_client = qdrant_client
        
        # Build the workflow graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for query processing."""
        workflow = StateGraph(QueryState)
        
        # Add nodes for each processing step
        workflow.add_node("embed_query", self._embed_query_node)
        workflow.add_node("search_vectors", self._search_vectors_node)
        workflow.add_node("assemble_results", self._assemble_results_node)
        
        # Define the workflow edges
        workflow.set_entry_point("embed_query")
        workflow.add_edge("embed_query", "search_vectors")
        workflow.add_edge("search_vectors", "assemble_results")
        workflow.add_edge("assemble_results", END)
        
        # Compile the graph with checkpointing
        return workflow.compile(checkpointer=MemorySaver())
    
    async def _embed_query_node(self, state: QueryState) -> QueryState:
        """
        Node 1: Convert query text to embedding vector.
        
        Handles:
        - Query text embedding using FastEmbed
        - Error handling for embedding failures
        """
        logger.info(f"Generating embedding for query: {state['query'][:50]}...")
        
        try:
            # Generate query embedding
            query_embedding = await self.embedder.embed_query(state["query"])
            
            logger.info(f"Generated query embedding with dimension {len(query_embedding)}")
            
            return {
                **state,
                "query_embedding": query_embedding
            }
            
        except Exception as e:
            logger.error(f"Error generating query embedding: {str(e)}")
            return {
                **state,
                "query_embedding": [],
                "errors": [f"Query embedding error: {str(e)}"]
            }
    
    async def _search_vectors_node(self, state: QueryState) -> QueryState:
        """
        Node 2: Perform similarity search in Qdrant.
        
        Handles:
        - Vector similarity search
        - Result filtering by score threshold
        - Connection error handling
        """
        logger.info(f"Searching for top {state['max_results']} similar documents")
        
        # Check if query embedding was successful
        if not state.get("query_embedding"):
            logger.warning("Skipping search due to embedding failure")
            return {
                **state,
                "search_results": []
            }
        
        try:
            # Perform similarity search
            search_results = await self.qdrant_client.search(
                query_vector=state["query_embedding"],
                top_k=state["max_results"],
                score_threshold=state.get("score_threshold")
            )
            
            logger.info(f"Found {len(search_results)} matching documents")
            
            return {
                **state,
                "search_results": search_results
            }
            
        except Exception as e:
            logger.error(f"Error during similarity search: {str(e)}")
            return {
                **state,
                "search_results": [],
                "errors": [f"Similarity search error: {str(e)}"]
            }
    
    async def _assemble_results_node(self, state: QueryState) -> QueryState:
        """
        Node 3: Assemble and format query results.
        
        Handles:
        - Converting search results to QueryResult objects
        - Including metadata and similarity scores
        - Result formatting
        """
        logger.info(f"Assembling {len(state['search_results'])} results")
        
        try:
            results = []
            
            for search_result in state["search_results"]:
                payload = search_result["payload"]
                
                # Create minimal CSV metadata from payload
                from app.models import CSVDocument
                
                csv_metadata = CSVDocument(
                    document_id=payload.get("document_id", ""),
                    source_file=payload.get("source_file", "unknown"),
                    row_number=payload.get("row_number", 0),
                    content={"chunk_content": payload.get("content", "")},
                    ingestion_time=datetime.fromisoformat(payload.get("ingestion_time", datetime.utcnow().isoformat()))
                )
                
                # Create QueryResult
                query_result = QueryResult(
                    document_id=payload.get("document_id", ""),
                    chunk_id=payload.get("chunk_id", search_result["id"]),
                    content=payload.get("content", ""),
                    similarity_score=search_result["score"],
                    metadata=payload,
                    csv_metadata=csv_metadata
                )
                
                results.append(query_result)
            
            logger.info(f"Successfully assembled {len(results)} query results")
            
            return {
                **state,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error assembling results: {str(e)}")
            return {
                **state,
                "results": [],
                "errors": [f"Result assembly error: {str(e)}"]
            }
    
    async def run(
        self,
        query: str,
        max_results: int = 10,
        score_threshold: Optional[float] = None
    ) -> List[QueryResult]:
        """
        Execute the query processing workflow.
        
        Args:
            query: User query text
            max_results: Maximum number of results to return
            score_threshold: Optional minimum similarity score threshold
            
        Returns:
            List of QueryResult objects
        """
        # Initialize state
        initial_state: QueryState = {
            "query": query,
            "max_results": max_results,
            "score_threshold": score_threshold,
            "query_embedding": [],
            "search_results": [],
            "results": [],
            "errors": []
        }
        
        try:
            # Run the workflow
            config = {"configurable": {"thread_id": f"query_{hash(query)}"}}
            final_state = await self.graph.ainvoke(initial_state, config)
            
            # Check for errors
            if final_state.get("errors"):
                logger.warning(f"Query completed with errors: {final_state['errors']}")
            
            return final_state.get("results", [])
            
        except Exception as e:
            logger.error(f"Query workflow execution failed: {str(e)}")
            return []


# ============================================================================
# Orchestrator - Main Interface
# ============================================================================

class Orchestrator:
    """
    Main orchestrator that manages both ingestion and query workflows.
    
    Provides high-level interface for:
    - CSV file ingestion
    - Document querying
    """
    
    def __init__(self, config: ServerConfig):
        """
        Initialize orchestrator with all required components.
        
        Args:
            config: Server configuration
        """
        self.config = config
        
        # Initialize components
        self.csv_parser = CSVParser(config)
        self.embedder = Embedder(
            model_name=config.embedding_model_name,
            batch_size=config.embedding_batch_size,
            enable_sparse=config.enable_sparse_embeddings,
            max_chunk_size=config.max_chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        self.qdrant_client = QdrantClient(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
            collection_name=config.qdrant_collection_name
        )
        
        # Initialize workflows
        self.ingestion_workflow = CSVIngestionWorkflow(
            csv_parser=self.csv_parser,
            embedder=self.embedder,
            qdrant_client=self.qdrant_client
        )
        
        self.query_workflow = QueryProcessingWorkflow(
            embedder=self.embedder,
            qdrant_client=self.qdrant_client
        )
        
        logger.info("Orchestrator initialized with all components")
    
    async def ingest_csv(self, file_path: str) -> IngestionStatus:
        """
        Ingest a CSV file into the vector database.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            IngestionStatus with results and errors
        """
        logger.info(f"Starting CSV ingestion for: {file_path}")
        return await self.ingestion_workflow.run(file_path)
    
    async def query(
        self,
        query: str,
        max_results: int = 10,
        score_threshold: Optional[float] = None
    ) -> List[QueryResult]:
        """
        Query documents using natural language.
        
        Args:
            query: User query text
            max_results: Maximum number of results to return
            score_threshold: Optional minimum similarity score
            
        Returns:
            List of QueryResult objects
        """
        logger.info(f"Processing query: {query[:50]}...")
        return await self.query_workflow.run(query, max_results, score_threshold)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all components.
        
        Returns:
            Dictionary with component health status
        """
        with logfire.span("orchestrator.health_check"):
            health_status = {
                "csv_parser": "ok",
                "embedder": "ok",
                "qdrant": "unknown"
            }
            
            try:
                # Check Qdrant connection
                qdrant_healthy = await self.qdrant_client.health_check()
                health_status["qdrant"] = "ok" if qdrant_healthy else "error"
            except Exception as e:
                logger.error(f"Qdrant health check failed: {e}")
                logfire.error("Qdrant health check failed in orchestrator", error=str(e))
                health_status["qdrant"] = "error"
            
            logfire.info("Health check completed", health_status=health_status)
            return health_status
    
    async def close(self):
        """Close all component connections."""
        try:
            await self.qdrant_client.close()
            logger.info("Orchestrator closed successfully")
        except Exception as e:
            logger.error(f"Error closing orchestrator: {e}")
