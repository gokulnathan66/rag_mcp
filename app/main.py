import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import logfire
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .config import ServerConfig
from .models import QueryResult, ErrorResponse, ServerStatus, IngestionStatus
from .orchestrator import Orchestrator


# Configure logging
logger = logging.getLogger(__name__)


# Configure Pydantic Logfire for monitoring and debugging
def setup_logfire(config: ServerConfig) -> None:
    """Configure Pydantic Logfire for monitoring and debugging."""
    if config.enable_logfire:
        try:
            logfire.configure(
                service_name=config.mcp_server_name,
                service_version=config.mcp_version,
            )
            # Set up logging level
            logging.basicConfig(level=getattr(logging, config.log_level.upper()))
            logger.info(f"Logfire configured for {config.mcp_server_name} v{config.mcp_version}")
        except Exception as e:
            # Fallback to basic logging if logfire setup fails
            logging.basicConfig(level=getattr(logging, config.log_level.upper()))
            logger.warning(f"Logfire setup failed, using basic logging: {e}")
    else:
        # Set up basic logging when logfire is disabled
        logging.basicConfig(level=getattr(logging, config.log_level.upper()))


# MCP Tool Input Models
class IngestCSVInput(BaseModel):
    """Input model for ingest_csv MCP tool."""
    file_path: str = Field(..., description="Path to the CSV file to ingest")


class QueryDocumentsInput(BaseModel):
    """Input model for query_documents MCP tool."""
    query: str = Field(..., description="Natural language query to search for relevant documents")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum number of results to return")
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum similarity score threshold")


# Global orchestrator instance and lifecycle management
_orchestrator: Optional[Orchestrator] = None
_server_start_time: Optional[datetime] = None
_shutdown_event: Optional[asyncio.Event] = None


def get_orchestrator(config: ServerConfig) -> Orchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        logger.info("Initializing orchestrator...")
        _orchestrator = Orchestrator(config)
        logger.info("Orchestrator initialized successfully")
    return _orchestrator


async def initialize_components(config: ServerConfig) -> Orchestrator:
    """
    Initialize all application components with proper startup sequence.
    
    This function ensures components are initialized in the correct order:
    1. Orchestrator (which initializes CSV parser, embedder, and Qdrant client)
    2. Qdrant collection setup
    3. Health checks
    
    Args:
        config: Server configuration
        
    Returns:
        Initialized Orchestrator instance
        
    Raises:
        Exception: If component initialization fails
    """
    logger.info("Starting component initialization...")
    
    try:
        # Initialize orchestrator (this creates all sub-components)
        orchestrator = get_orchestrator(config)
        
        # Ensure Qdrant collection exists
        logger.info(f"Ensuring Qdrant collection '{config.qdrant_collection_name}' exists...")
        await orchestrator.qdrant_client.ensure_collection(
            collection_name=config.qdrant_collection_name,
            vector_size=384  # Default for all-MiniLM-L6-v2
        )
        logger.info("Qdrant collection ready")
        
        # Perform initial health check
        logger.info("Performing initial health check...")
        health_status = await orchestrator.health_check()
        
        # Log component status
        for component, status in health_status.items():
            if status == "ok":
                logger.info(f"✓ {component}: healthy")
            else:
                logger.warning(f"✗ {component}: {status}")
        
        # Check if critical components are healthy
        if health_status.get("qdrant") != "ok":
            logger.error("Critical component Qdrant is not healthy!")
            raise Exception("Qdrant connection failed during initialization")
        
        logger.info("All components initialized successfully")
        return orchestrator
        
    except Exception as e:
        logger.error(f"Component initialization failed: {str(e)}", exc_info=True)
        raise


async def shutdown_components(orchestrator: Optional[Orchestrator] = None):
    """
    Gracefully shutdown all application components.
    
    This function ensures proper cleanup of resources:
    1. Close Qdrant client connections
    2. Cleanup orchestrator resources
    3. Shutdown thread pools and async tasks
    
    Args:
        orchestrator: Optional orchestrator instance to shutdown
    """
    logger.info("Starting graceful shutdown...")
    
    try:
        if orchestrator:
            # Close orchestrator and all its components
            await orchestrator.close()
            logger.info("Orchestrator closed successfully")
        
        # Clear global state
        global _orchestrator
        _orchestrator = None
        
        logger.info("Shutdown completed successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}", exc_info=True)


# Initialize FastMCP server
def create_mcp_server(config: ServerConfig) -> FastMCP:
    """
    Create and configure the FastMCP server with RAG tools.
    
    Implements MCP protocol compliance with:
    - JSON-RPC 2.0 handling (provided by FastMCP)
    - Server discovery and capability advertisement
    - Structured error responses
    - Tool registration and metadata
    - Proper lifecycle management with startup/shutdown hooks
    
    Args:
        config: Server configuration
        
    Returns:
        Configured FastMCP server instance
    """
    global _server_start_time, _shutdown_event
    _server_start_time = datetime.now(timezone.utc)
    _shutdown_event = asyncio.Event()
    
    # Set up Logfire monitoring
    setup_logfire(config)
    
    # Create FastMCP server instance with metadata for discovery
    mcp = FastMCP(
        name=config.mcp_server_name,
        version=config.mcp_version
    )
    
    logger.info(f"Creating FastMCP server: {config.mcp_server_name} v{config.mcp_version}")
    
    # Get orchestrator reference for tools
    def get_orchestrator_safe() -> Orchestrator:
        """Get orchestrator with safety check."""
        orchestrator = get_orchestrator(config)
        if orchestrator is None:
            raise Exception("Orchestrator not initialized. Server may not have started properly.")
        return orchestrator
    
    @mcp.tool()
    async def ingest_csv(input_data: IngestCSVInput) -> IngestionStatus:
        """
        Ingest documents from a CSV file into the vector database.
        
        This tool:
        1. Parses the CSV file and extracts documents
        2. Chunks large documents into manageable segments
        3. Generates embeddings using FastEmbed
        4. Stores vectors in Qdrant database
        
        Args:
            input_data: Contains file_path to the CSV file
            
        Returns:
            IngestionStatus with processing results and any errors
            
        Raises:
            Exception: If ingestion fails with detailed error information
        """
        from .errors import handle_exception, log_error, RAGError
        
        correlation_id = str(uuid.uuid4())
        
        with logfire.span(
            "ingest_csv",
            file_path=input_data.file_path,
            correlation_id=correlation_id
        ):
            try:
                logger.info(f"[{correlation_id}] Starting CSV ingestion: {input_data.file_path}")
                
                # Get orchestrator instance
                orchestrator = get_orchestrator_safe()
                
                # Execute ingestion workflow through orchestrator
                result = await orchestrator.ingest_csv(input_data.file_path)
                
                logger.info(
                    f"[{correlation_id}] CSV ingestion completed: "
                    f"status={result.status}, docs={result.documents_processed}, "
                    f"chunks={result.chunks_created}, embeddings={result.embeddings_generated}"
                )
                
                return result
                
            except RAGError as e:
                # Handle structured RAG errors
                log_error(e, context={'operation': 'ingest_csv', 'file_path': input_data.file_path})
                logfire.error(
                    f"CSV ingestion failed: {e.message}",
                    correlation_id=e.correlation_id,
                    error_code=e.code
                )
                
                return IngestionStatus(
                    status="failed",
                    collection_name=input_data.file_path,
                    documents_processed=0,
                    chunks_created=0,
                    embeddings_generated=0,
                    errors=[f"{e.code}: {e.message} (correlation_id: {e.correlation_id})"]
                )
                
            except Exception as e:
                # Handle unexpected errors
                error_response = handle_exception(e, "ingest_csv", correlation_id)
                logfire.error(
                    f"Unexpected error during CSV ingestion: {str(e)}",
                    correlation_id=correlation_id
                )
                
                return IngestionStatus(
                    status="failed",
                    collection_name=input_data.file_path,
                    documents_processed=0,
                    chunks_created=0,
                    embeddings_generated=0,
                    errors=[f"{error_response.error_code}: {error_response.error_message} (correlation_id: {correlation_id})"]
                )
    
    @mcp.tool()
    async def query_documents(input_data: QueryDocumentsInput) -> List[QueryResult]:
        """
        Query documents using natural language and vector similarity search.
        
        This tool:
        1. Converts the query to an embedding vector using FastEmbed
        2. Performs similarity search in Qdrant vector database
        3. Returns relevant documents ranked by similarity score
        
        Args:
            input_data: Contains query text, max_results, and optional score_threshold
            
        Returns:
            List of QueryResult objects with matching documents and similarity scores
            
        Raises:
            Exception: If query processing fails with detailed error information
        """
        from .errors import handle_exception, log_error, RAGError, to_error_response
        
        correlation_id = str(uuid.uuid4())
        
        with logfire.span(
            "query_documents",
            query=input_data.query[:100],  # Truncate for logging
            max_results=input_data.max_results,
            score_threshold=input_data.score_threshold,
            correlation_id=correlation_id
        ):
            try:
                logger.info(
                    f"[{correlation_id}] Processing query: '{input_data.query[:50]}...' "
                    f"(max_results={input_data.max_results})"
                )
                
                # Get orchestrator instance
                orchestrator = get_orchestrator_safe()
                
                # Execute query workflow through orchestrator
                results = await orchestrator.query(
                    query=input_data.query,
                    max_results=input_data.max_results,
                    score_threshold=input_data.score_threshold
                )
                
                logger.info(f"[{correlation_id}] Query completed: {len(results)} results found")
                
                return results
                
            except RAGError as e:
                # Handle structured RAG errors
                log_error(e, context={'operation': 'query_documents', 'query': input_data.query[:100]})
                error_response = to_error_response(e)
                logfire.error(
                    f"Query processing failed: {e.message}",
                    correlation_id=e.correlation_id,
                    error_code=e.code
                )
                
                # Re-raise with structured error information
                raise Exception(
                    f"{error_response.error_code}: {error_response.error_message} "
                    f"(correlation_id: {error_response.correlation_id})"
                )
                
            except Exception as e:
                # Handle unexpected errors
                error_response = handle_exception(e, "query_documents", correlation_id)
                logfire.error(
                    f"Unexpected error during query processing: {str(e)}",
                    correlation_id=correlation_id
                )
                
                # Re-raise with correlation ID for client error handling
                raise Exception(
                    f"{error_response.error_code}: {error_response.error_message} "
                    f"(correlation_id: {correlation_id})"
                )
    
    @mcp.tool()
    async def get_server_status() -> ServerStatus:
        """
        Get the current status of the RAG MCP server and its components.
        
        Returns health status for:
        - Overall server status
        - CSV parser component
        - FastEmbed embedder component
        - Qdrant vector database connection
        - LangGraph orchestrator
        
        Returns:
            ServerStatus with component health information
        """
        from .errors import handle_exception
        
        correlation_id = str(uuid.uuid4())
        
        with logfire.span("get_server_status", correlation_id=correlation_id):
            try:
                logger.info(f"[{correlation_id}] Getting server status")
                
                # Calculate uptime
                uptime_seconds = None
                if _server_start_time:
                    uptime_seconds = (datetime.now(timezone.utc) - _server_start_time).total_seconds()
                
                # Get orchestrator instance safely
                try:
                    orchestrator = get_orchestrator_safe()
                    # Get component health status
                    health_status = await orchestrator.health_check()
                except Exception as e:
                    logger.warning(f"Could not get orchestrator for health check: {e}")
                    health_status = {
                        "csv_parser": "unknown",
                        "embedder": "unknown",
                        "qdrant": "unknown"
                    }
                
                # Map health check results to component status
                components = {
                    "csv_parser": health_status.get("csv_parser", "unknown"),
                    "fastembed": health_status.get("embedder", "unknown"),
                    "qdrant_client": health_status.get("qdrant", "unknown"),
                    "langgraph": "ok"  # If orchestrator is running, LangGraph is ok
                }
                
                # Determine overall status
                if all(status == "ok" for status in components.values()):
                    overall_status = "running"
                elif any(status == "error" for status in components.values()):
                    overall_status = "error"
                else:
                    overall_status = "running"  # Partial functionality
                
                logger.info(
                    f"[{correlation_id}] Server status: {overall_status}, "
                    f"components: {components}"
                )
                
                return ServerStatus(
                    server_name=config.mcp_server_name,
                    version=config.mcp_version,
                    status=overall_status,
                    uptime_seconds=uptime_seconds,
                    components=components,
                    last_health_check=datetime.now(timezone.utc)
                )
                
            except Exception as e:
                # Handle errors gracefully and return error status
                error_response = handle_exception(e, "get_server_status", correlation_id)
                logger.error(
                    f"[{correlation_id}] Error getting server status: {str(e)}",
                    exc_info=True
                )
                logfire.error(
                    f"Server status check failed: {error_response.error_message}",
                    correlation_id=correlation_id
                )
                
                # Return error status with available information
                uptime_seconds = None
                if _server_start_time:
                    uptime_seconds = (datetime.now(timezone.utc) - _server_start_time).total_seconds()
                
                return ServerStatus(
                    server_name=config.mcp_server_name,
                    version=config.mcp_version,
                    status="error",
                    uptime_seconds=uptime_seconds,
                    components={
                        "csv_parser": "unknown",
                        "fastembed": "unknown",
                        "qdrant_client": "unknown",
                        "langgraph": "unknown"
                    },
                    last_health_check=datetime.now(timezone.utc)
                )
    
    logger.info("FastMCP server created with tools: ingest_csv, query_documents, get_server_status")
    return mcp


# Main application entry point with proper lifecycle management
def main():
    """
    Main application entry point.
    
    This function:
    1. Loads configuration from environment
    2. Initializes all components in correct order
    3. Creates and configures the FastMCP server
    4. Starts the server and handles graceful shutdown
    
    The initialization happens synchronously before FastMCP.run() is called,
    ensuring all components are ready before accepting requests.
    """
    orchestrator = None
    
    try:
        # Load configuration
        config = ServerConfig()
        
        logger.info("=" * 60)
        logger.info(f"Starting {config.mcp_server_name} v{config.mcp_version}")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        logger.info(f"  CSV directory: {config.csv_data_directory}")
        logger.info(f"  Qdrant URL: {config.qdrant_url}")
        logger.info(f"  Qdrant collection: {config.qdrant_collection_name}")
        logger.info(f"  Embedding model: {config.embedding_model_name}")
        logger.info(f"  Max chunk size: {config.max_chunk_size}")
        logger.info(f"  Chunk overlap: {config.chunk_overlap}")
        logger.info(f"  Logfire enabled: {config.enable_logfire}")
        logger.info(f"  Log level: {config.log_level}")
        logger.info("=" * 60)
        
        # Initialize all components using asyncio
        logger.info("Initializing components...")
        orchestrator = asyncio.run(initialize_components(config))
        logger.info("✓ All components initialized successfully")
        
        # Create MCP server
        logger.info("Creating FastMCP server...")
        mcp_server = create_mcp_server(config)
        logger.info("✓ FastMCP server created")
        
        # Start the server (FastMCP handles the asyncio loop internally)
        logger.info("=" * 60)
        logger.info("FastMCP server is ready to accept connections")
        logger.info("=" * 60)
        
        # Run the server - this blocks until shutdown
        # FastMCP.run() creates its own event loop
        mcp_server.run()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        raise
    finally:
        # Ensure cleanup happens
        if orchestrator:
            logger.info("Cleaning up resources...")
            try:
                asyncio.run(shutdown_components(orchestrator))
                logger.info("✓ Cleanup completed")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    main()
