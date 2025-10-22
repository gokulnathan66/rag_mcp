import asyncio
import logging
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import logfire
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .config import ServerConfig
from .models import QueryResult, ErrorResponse, ServerStatus, IngestionStatus
from .orchestrator import Orchestrator
from .http_monitoring import HTTPMonitor, initialize_http_monitor, shutdown_http_monitor, get_http_monitor
from .http_connection_manager import HTTPConnectionManager, initialize_connection_manager, shutdown_connection_manager, get_connection_manager
from .http_health_check import HTTPHealthChecker, setup_health_check_endpoint


# Configure logging
logger = logging.getLogger(__name__)


# Configure Pydantic Logfire for monitoring and debugging
def setup_logfire(config: ServerConfig) -> None:
    """Configure Pydantic Logfire for monitoring and debugging."""
    if config.enable_logfire:
        try:
            # Configure Logfire with transport-specific metadata
            logfire_config = {
                "service_name": config.mcp_server_name,
                "service_version": config.mcp_version,
            }
            
            # Add HTTP transport metadata if enabled
            if config.transport_mode == "http":
                logfire_config.update({
                    "tags": {
                        "transport": "http",
                        "http_host": config.http_transport.http_host,
                        "http_port": str(config.http_transport.http_port),
                        "max_connections": str(config.http_transport.max_concurrent_connections)
                    }
                })
            else:
                logfire_config.update({
                    "tags": {
                        "transport": "stdio"
                    }
                })
            
            logfire.configure(**logfire_config)
            
            # Set up logging level
            logging.basicConfig(level=getattr(logging, config.log_level.upper()))
            logger.info(f"Logfire configured for {config.mcp_server_name} v{config.mcp_version}")
            
            if config.transport_mode == "http":
                logger.info("HTTP transport monitoring enabled in Logfire")
                
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
_http_connection_manager: Optional[HTTPConnectionManager] = None
_http_health_checker: Optional[HTTPHealthChecker] = None
_shutdown_requested: bool = False


def setup_signal_handlers():
    """
    Set up signal handlers for graceful shutdown in containerized environments.
    
    This function configures handlers for SIGTERM and SIGINT signals to ensure
    proper cleanup when the container is stopped or receives shutdown signals.
    """
    global _shutdown_requested
    
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
        _shutdown_requested = True
        
        # Set shutdown event if available
        if _shutdown_event and not _shutdown_event.is_set():
            _shutdown_event.set()
    
    # Register signal handlers for graceful shutdown
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Registered SIGTERM handler for graceful shutdown")
    
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("Registered SIGINT handler for graceful shutdown")


async def wait_for_shutdown_signal():
    """
    Wait for shutdown signal or event.
    
    This function can be used to wait for shutdown signals in async contexts,
    particularly useful for containerized deployments where we need to handle
    SIGTERM signals from container orchestrators.
    
    Returns:
        True if shutdown was requested, False otherwise
    """
    global _shutdown_requested, _shutdown_event
    
    # Check if shutdown was already requested
    if _shutdown_requested:
        return True
    
    # Wait for shutdown event if available
    if _shutdown_event:
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=1.0)
            return True
        except asyncio.TimeoutError:
            return _shutdown_requested
    
    # Fallback: just check the flag
    return _shutdown_requested


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


async def initialize_http_transport_components(config: ServerConfig) -> None:
    """
    Initialize HTTP transport specific components.
    
    This function initializes:
    1. HTTP monitoring
    2. HTTP connection manager
    3. HTTP health checker (if enabled)
    
    Args:
        config: Server configuration with HTTP transport settings
    """
    global _http_connection_manager, _http_health_checker
    
    if config.transport_mode != "http":
        return
    
    logger.info("Initializing HTTP transport components...")
    
    try:
        # Initialize HTTP monitor
        http_monitor = initialize_http_monitor(
            max_connections=config.http_transport.max_concurrent_connections
        )
        logger.info("✓ HTTP monitor initialized")
        
        # Initialize HTTP connection manager
        _http_connection_manager = initialize_connection_manager(
            config.http_transport,
            http_monitor
        )
        await _http_connection_manager.start()
        logger.info("✓ HTTP connection manager initialized and started")
        
        # Initialize HTTP health checker
        if config.http_transport.enable_health_endpoint:
            logger.info("✓ HTTP health checker will be available via MCP tool")
        
        logger.info("HTTP transport components initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize HTTP transport components: {str(e)}", exc_info=True)
        raise


async def shutdown_components(orchestrator: Optional[Orchestrator] = None, timeout: int = 30):
    """
    Gracefully shutdown all application components with timeout handling.
    
    This function ensures proper cleanup of resources with container-friendly timeouts:
    1. Shutdown HTTP transport components
    2. Close active connections gracefully
    3. Close Qdrant client connections
    4. Cleanup orchestrator resources
    5. Shutdown thread pools and async tasks
    
    Args:
        orchestrator: Optional orchestrator instance to shutdown
        timeout: Maximum time to wait for shutdown completion (seconds)
    """
    logger.info(f"Starting graceful shutdown (timeout: {timeout}s)...")
    
    shutdown_start = datetime.now(timezone.utc)
    
    try:
        # Shutdown HTTP transport components with timeout
        global _http_connection_manager, _http_health_checker
        
        if _http_connection_manager:
            logger.info("Shutting down HTTP connection manager...")
            try:
                await asyncio.wait_for(
                    shutdown_connection_manager(),
                    timeout=min(10, timeout // 3)
                )
                logger.info("✓ HTTP connection manager shutdown completed")
            except asyncio.TimeoutError:
                logger.warning("HTTP connection manager shutdown timed out, forcing cleanup")
            except Exception as e:
                logger.error(f"Error shutting down HTTP connection manager: {e}")
        
        # Shutdown HTTP monitor
        try:
            shutdown_http_monitor()
            logger.info("✓ HTTP monitor shutdown completed")
        except Exception as e:
            logger.error(f"Error shutting down HTTP monitor: {e}")
        
        if orchestrator:
            logger.info("Shutting down orchestrator and components...")
            try:
                # Close orchestrator and all its components with timeout
                await asyncio.wait_for(
                    orchestrator.close(),
                    timeout=min(15, timeout * 2 // 3)
                )
                logger.info("✓ Orchestrator closed successfully")
            except asyncio.TimeoutError:
                logger.warning("Orchestrator shutdown timed out, forcing cleanup")
            except Exception as e:
                logger.error(f"Error shutting down orchestrator: {e}")
        
        # Clear global state
        global _orchestrator, _shutdown_requested
        _orchestrator = None
        _http_connection_manager = None
        _http_health_checker = None
        _shutdown_requested = False
        
        shutdown_duration = (datetime.now(timezone.utc) - shutdown_start).total_seconds()
        logger.info(f"Shutdown completed successfully in {shutdown_duration:.2f}s")
        
        # Log shutdown metrics
        logfire.info(
            "Graceful shutdown completed",
            shutdown_duration_seconds=shutdown_duration,
            timeout_seconds=timeout,
            components_shutdown=["http_connection_manager", "http_monitor", "orchestrator"],
            shutdown_type="graceful"
        )
        
    except Exception as e:
        shutdown_duration = (datetime.now(timezone.utc) - shutdown_start).total_seconds()
        logger.error(f"Error during shutdown after {shutdown_duration:.2f}s: {str(e)}", exc_info=True)
        
        # Log shutdown error metrics
        logfire.error(
            "Shutdown error occurred",
            error=str(e),
            shutdown_duration_seconds=shutdown_duration,
            timeout_seconds=timeout,
            shutdown_type="error"
        )


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
    - HTTP transport support for network deployment
    
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
    
    # Validate HTTP transport configuration if enabled
    if config.transport_mode == "http":
        validation_errors = config.validate_http_transport_config()
        if validation_errors:
            error_msg = "HTTP transport configuration validation failed: " + "; ".join(validation_errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Enable HTTP transport in configuration
        config.http_transport.enable_http_transport = True
        logger.info(f"HTTP transport enabled: {config.http_transport.http_host}:{config.http_transport.http_port}")
    
    # Create FastMCP server instance with metadata for discovery
    mcp = FastMCP(
        name=config.mcp_server_name,
        version=config.mcp_version
    )
    
    logger.info(f"Creating FastMCP server: {config.mcp_server_name} v{config.mcp_version}")
    logger.info(f"Transport mode: {config.transport_mode}")
    
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
        
        # Add HTTP transport context to monitoring
        span_context = {
            "file_path": input_data.file_path,
            "correlation_id": correlation_id,
            "transport_mode": config.transport_mode
        }
        
        if config.transport_mode == "http":
            span_context.update({
                "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                "operation_type": "http_mcp_tool"
            })
        
        with logfire.span("ingest_csv", **span_context):
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
                error_context = {
                    "correlation_id": e.correlation_id,
                    "error_code": e.code,
                    "transport_mode": config.transport_mode
                }
                
                if config.transport_mode == "http":
                    error_context.update({
                        "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                        "error_type": "http_mcp_tool_error"
                    })
                
                logfire.error(
                    f"CSV ingestion failed: {e.message}",
                    **error_context
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
                error_context = {
                    "correlation_id": correlation_id,
                    "transport_mode": config.transport_mode
                }
                
                if config.transport_mode == "http":
                    error_context.update({
                        "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                        "error_type": "http_mcp_tool_error"
                    })
                
                logfire.error(
                    f"Unexpected error during CSV ingestion: {str(e)}",
                    **error_context
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
        
        # Add HTTP transport context to monitoring
        span_context = {
            "query": input_data.query[:100],  # Truncate for logging
            "max_results": input_data.max_results,
            "score_threshold": input_data.score_threshold,
            "correlation_id": correlation_id,
            "transport_mode": config.transport_mode
        }
        
        if config.transport_mode == "http":
            span_context.update({
                "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                "operation_type": "http_mcp_tool"
            })
        
        with logfire.span("query_documents", **span_context):
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
                error_context = {
                    "correlation_id": e.correlation_id,
                    "error_code": e.code,
                    "transport_mode": config.transport_mode
                }
                
                if config.transport_mode == "http":
                    error_context.update({
                        "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                        "error_type": "http_mcp_tool_error"
                    })
                
                logfire.error(
                    f"Query processing failed: {e.message}",
                    **error_context
                )
                
                # Re-raise with structured error information
                raise Exception(
                    f"{error_response.error_code}: {error_response.error_message} "
                    f"(correlation_id: {error_response.correlation_id})"
                )
                
            except Exception as e:
                # Handle unexpected errors
                error_response = handle_exception(e, "query_documents", correlation_id)
                error_context = {
                    "correlation_id": correlation_id,
                    "transport_mode": config.transport_mode
                }
                
                if config.transport_mode == "http":
                    error_context.update({
                        "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                        "error_type": "http_mcp_tool_error"
                    })
                
                logfire.error(
                    f"Unexpected error during query processing: {str(e)}",
                    **error_context
                )
                
                # Re-raise with correlation ID for client error handling
                raise Exception(
                    f"{error_response.error_code}: {error_response.error_message} "
                    f"(correlation_id: {correlation_id})"
                )
    
    @mcp.tool()
    async def get_http_health() -> Dict[str, Any]:
        """
        Get HTTP transport health status for load balancer integration.
        
        This tool provides comprehensive health information specifically
        for HTTP transport including connection statistics, metrics,
        and component status.
        
        Returns:
            HTTP health status dictionary with detailed transport information
        """
        from .http_health_check import HTTPHealthChecker
        from .errors import handle_exception
        
        correlation_id = str(uuid.uuid4())
        
        # Add HTTP transport context to monitoring
        span_context = {
            "correlation_id": correlation_id,
            "transport_mode": config.transport_mode,
            "operation_type": "http_health_check"
        }
        
        if config.transport_mode == "http":
            span_context.update({
                "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                "health_endpoint_enabled": config.http_transport.enable_health_endpoint
            })
        
        with logfire.span("get_http_health", **span_context):
            try:
                logger.info(f"[{correlation_id}] Getting HTTP health status")
                
                if config.transport_mode != "http":
                    return {
                        "status": "not_applicable",
                        "message": "HTTP transport not enabled",
                        "transport_mode": config.transport_mode,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                
                # Get base server status
                server_status = await get_server_status()
                
                # Get HTTP-specific information
                http_info = {
                    "transport_mode": "http",
                    "host": config.http_transport.http_host,
                    "port": config.http_transport.http_port,
                    "max_connections": config.http_transport.max_concurrent_connections,
                    "connection_timeout": config.http_transport.connection_timeout,
                    "cors_enabled": config.http_transport.enable_cors,
                    "health_endpoint_enabled": config.http_transport.enable_health_endpoint
                }
                
                # Add connection manager stats if available
                global _http_connection_manager
                if _http_connection_manager:
                    try:
                        conn_stats = await _http_connection_manager.get_connection_stats()
                        http_info.update({
                            "connection_stats": conn_stats
                        })
                    except Exception as e:
                        logger.warning(f"Failed to get connection stats: {e}")
                        http_info["connection_stats_error"] = str(e)
                
                # Add HTTP monitor metrics if available
                http_monitor = get_http_monitor()
                if http_monitor:
                    try:
                        http_metrics = await http_monitor.get_metrics()
                        http_info.update({
                            "http_metrics": {
                                "total_requests": http_metrics.total_requests,
                                "successful_requests": http_metrics.successful_requests,
                                "failed_requests": http_metrics.failed_requests,
                                "avg_response_time": http_metrics.avg_response_time,
                                "error_rate": http_metrics.error_rate,
                                "last_updated": http_metrics.last_updated.isoformat()
                            }
                        })
                    except Exception as e:
                        logger.warning(f"Failed to get HTTP metrics: {e}")
                        http_info["http_metrics_error"] = str(e)
                
                # Determine overall HTTP health status
                if server_status.status == "error":
                    http_status = "unhealthy"
                elif server_status.components.get("qdrant_client") == "error":
                    http_status = "unhealthy"
                elif http_info.get("connection_stats", {}).get("connection_utilization", 0) > 90:
                    http_status = "degraded"
                elif http_info.get("http_metrics", {}).get("error_rate", 0) > 10:
                    http_status = "degraded"
                else:
                    http_status = "healthy"
                
                health_response = {
                    "status": http_status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "server_name": server_status.server_name,
                    "version": server_status.version,
                    "uptime_seconds": server_status.uptime_seconds,
                    "components": server_status.components,
                    "http_transport": http_info
                }
                
                logger.info(
                    f"[{correlation_id}] HTTP health check completed: {http_status} "
                    f"(active_connections: {http_info.get('connection_stats', {}).get('active_connections', 0)})"
                )
                
                return health_response
                
            except Exception as e:
                # Handle errors gracefully
                error_response = handle_exception(e, "get_http_health", correlation_id)
                logger.error(
                    f"[{correlation_id}] Error getting HTTP health status: {str(e)}",
                    exc_info=True
                )
                
                error_context = {
                    "correlation_id": correlation_id,
                    "transport_mode": config.transport_mode
                }
                
                if config.transport_mode == "http":
                    error_context.update({
                        "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                        "error_type": "http_health_check_error"
                    })
                
                logfire.error(
                    f"HTTP health check failed: {error_response.error_message}",
                    **error_context
                )
                
                # Return error status
                return {
                    "status": "unhealthy",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": f"{error_response.error_code}: {error_response.error_message}",
                    "correlation_id": correlation_id,
                    "transport_mode": config.transport_mode,
                    "http_transport": {"status": "error", "error": str(e)}
                }

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
        
        # Add HTTP transport context to monitoring
        span_context = {
            "correlation_id": correlation_id,
            "transport_mode": config.transport_mode
        }
        
        if config.transport_mode == "http":
            span_context.update({
                "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                "operation_type": "http_mcp_tool"
            })
        
        with logfire.span("get_server_status", **span_context):
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
                error_context = {
                    "correlation_id": correlation_id,
                    "transport_mode": config.transport_mode
                }
                
                if config.transport_mode == "http":
                    error_context.update({
                        "http_endpoint": f"{config.http_transport.http_host}:{config.http_transport.http_port}",
                        "error_type": "http_mcp_tool_error"
                    })
                
                logfire.error(
                    f"Server status check failed: {error_response.error_message}",
                    **error_context
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
    
    tools_list = ["ingest_csv", "query_documents", "get_server_status"]
    if config.transport_mode == "http":
        tools_list.append("get_http_health")
        
        # Add HTTP health check endpoint if HTTP transport is enabled
        if config.http_transport.enable_health_endpoint:
            _setup_http_health_endpoint(mcp, config, get_server_status)
    
    logger.info(f"FastMCP server created with tools: {', '.join(tools_list)}")
    return mcp


def _setup_http_health_endpoint(mcp: FastMCP, config: ServerConfig, get_server_status_func):
    """
    Set up HTTP health check endpoint on the FastMCP HTTP app.
    
    This function adds a direct HTTP endpoint for health checks that can be
    accessed by load balancers and monitoring systems without using the MCP protocol.
    
    Args:
        mcp: FastMCP server instance
        config: Server configuration
        get_server_status_func: Function to get server status
    """
    from .http_health_check import HTTPHealthChecker, create_standalone_health_check_response
    from .http_connection_manager import get_connection_manager
    from .http_monitoring import get_http_monitor
    from .errors import handle_exception
    
    try:
        # Get the HTTP app from FastMCP
        http_app = mcp.http_app()
        
        # Create health checker instance
        health_checker = HTTPHealthChecker(
            config=config.http_transport,
            get_server_status_func=get_server_status_func,
            connection_manager=get_connection_manager(),
            http_monitor=get_http_monitor()
        )
        
        # Add the health check route
        @http_app.route(config.http_transport.health_check_path, methods=["GET"])
        async def health_check_endpoint(request):
            """
            HTTP health check endpoint for load balancer integration.
            
            Returns comprehensive health status including:
            - Overall server status
            - Component health status  
            - HTTP transport metrics
            - Connection statistics
            """
            from starlette.responses import JSONResponse
            
            try:
                # Perform health check
                health_status = await health_checker.check_health()
                
                # Convert to dict for JSON response
                health_dict = health_status.dict()
                
                # Return appropriate HTTP status code based on health
                if health_status.status == "healthy":
                    status_code = 200
                elif health_status.status == "degraded":
                    status_code = 200  # Still operational but with issues
                else:  # unhealthy
                    status_code = 503  # Service Unavailable
                
                return JSONResponse(
                    status_code=status_code,
                    content=health_dict
                )
                
            except Exception as e:
                # Handle health check errors gracefully
                correlation_id = f"health_error_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                error_response = handle_exception(e, "http_health_endpoint", correlation_id)
                
                logger.error(f"Health check endpoint error: {e}", exc_info=True)
                
                logfire.error(
                    "Health check endpoint error",
                    error=str(e),
                    correlation_id=correlation_id,
                    component="http_health_endpoint"
                )
                
                # Return error response using standalone function
                error_health = create_standalone_health_check_response(
                    server_name=config.mcp_server_name,
                    version=config.mcp_version,
                    status="unhealthy",
                    error=f"Health check failed: {str(e)}"
                )
                
                return JSONResponse(
                    status_code=503,
                    content=error_health
                )
        
        logger.info(f"HTTP health check endpoint configured at {config.http_transport.health_check_path}")
        
        logfire.info(
            "HTTP health check endpoint configured",
            path=config.http_transport.health_check_path,
            enabled=config.http_transport.enable_health_endpoint,
            component="http_health_endpoint"
        )
        
    except Exception as e:
        logger.error(f"Failed to setup HTTP health check endpoint: {e}", exc_info=True)
        
        logfire.error(
            "Failed to setup HTTP health check endpoint",
            error=str(e),
            component="http_health_endpoint"
        )


# Main application entry point with proper lifecycle management
def main():
    """
    Main application entry point with container lifecycle management.
    
    This function:
    1. Sets up signal handlers for graceful shutdown
    2. Loads configuration from environment
    3. Initializes all components in correct order
    4. Creates and configures the FastMCP server
    5. Starts the server and handles graceful shutdown
    6. Ensures proper cleanup for containerized deployments
    
    The initialization happens synchronously before FastMCP.run() is called,
    ensuring all components are ready before accepting requests.
    """
    orchestrator = None
    
    try:
        # Set up signal handlers for graceful shutdown (important for containers)
        setup_signal_handlers()
        
        # Load configuration
        config = ServerConfig()
        
        logger.info("=" * 60)
        logger.info(f"Starting {config.mcp_server_name} v{config.mcp_version}")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        logger.info(f"  Transport mode: {config.transport_mode}")
        if config.transport_mode == "http":
            logger.info(f"  HTTP host: {config.http_transport.http_host}")
            logger.info(f"  HTTP port: {config.http_transport.http_port}")
            logger.info(f"  Max connections: {config.http_transport.max_concurrent_connections}")
            logger.info(f"  Connection timeout: {config.http_transport.connection_timeout}s")
            logger.info(f"  CORS enabled: {config.http_transport.enable_cors}")
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
        
        # Initialize HTTP transport components if needed
        if config.transport_mode == "http":
            asyncio.run(initialize_http_transport_components(config))
            logger.info("✓ HTTP transport components initialized successfully")
        
        # Create MCP server
        logger.info("Creating FastMCP server...")
        mcp_server = create_mcp_server(config)
        logger.info("✓ FastMCP server created")
        
        # Start the server with transport-specific configuration
        logger.info("=" * 60)
        
        if config.transport_mode == "http":
            logger.info(f"Starting HTTP MCP server on {config.http_transport.http_host}:{config.http_transport.http_port}")
            logger.info(f"MCP endpoint: http://{config.http_transport.http_host}:{config.http_transport.http_port}/mcp/")
            if config.http_transport.enable_health_endpoint:
                logger.info(f"Health check: http://{config.http_transport.http_host}:{config.http_transport.http_port}{config.http_transport.health_check_path}")
            logger.info(f"Max concurrent connections: {config.http_transport.max_concurrent_connections}")
            logger.info(f"Connection timeout: {config.http_transport.connection_timeout}s")
            logger.info(f"CORS enabled: {config.http_transport.enable_cors}")
        else:
            logger.info("Starting MCP server with default transport (stdio)")
        
        logger.info("FastMCP server is ready to accept connections")
        logger.info("=" * 60)
        
        # Run the server with transport-specific parameters
        try:
            if config.transport_mode == "http":
                # Enhanced HTTP transport initialization logic
                logger.info("Initializing HTTP transport...")
                
                # Validate HTTP transport configuration before startup
                logger.info("Validating HTTP transport configuration...")
                validation_errors = config.validate_http_transport_config()
                if validation_errors:
                    error_msg = "HTTP transport validation failed: " + "; ".join(validation_errors)
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # Check host and port binding availability
                logger.info(f"Configuring host and port binding: {config.http_transport.http_host}:{config.http_transport.http_port}")
                
                # Prepare HTTP transport parameters
                http_params = {
                    "transport": "http",
                    "host": config.http_transport.http_host,
                    "port": config.http_transport.http_port
                }
                
                # Log HTTP server startup with comprehensive monitoring
                with logfire.span(
                    "http_server_startup",
                    transport_mode="http",
                    http_host=config.http_transport.http_host,
                    http_port=config.http_transport.http_port,
                    max_connections=config.http_transport.max_concurrent_connections,
                    connection_timeout=config.http_transport.connection_timeout,
                    cors_enabled=config.http_transport.enable_cors,
                    health_endpoint_enabled=config.http_transport.enable_health_endpoint
                ):
                    logger.info("Starting HTTP MCP server...")
                    logger.info(f"HTTP transport parameters: {http_params}")
                    
                    # Attempt to start HTTP server with proper error handling
                    try:
                        # Run with HTTP transport configuration
                        mcp_server.run(**http_params)
                    except OSError as os_error:
                        # Handle specific OS-level errors during HTTP server startup
                        if os_error.errno == 98 or "Address already in use" in str(os_error):
                            error_msg = f"HTTP server startup failed: Port {config.http_transport.http_port} is already in use"
                            logger.error(error_msg)
                            logger.error("Troubleshooting steps:")
                            logger.error(f"  1. Check if another service is using port {config.http_transport.http_port}")
                            logger.error("  2. Change the HTTP_PORT environment variable to use a different port")
                            logger.error("  3. Kill any existing processes using this port")
                            raise OSError(f"Port {config.http_transport.http_port} already in use") from os_error
                        elif os_error.errno == 13 or "Permission denied" in str(os_error):
                            error_msg = f"HTTP server startup failed: Permission denied for port {config.http_transport.http_port}"
                            logger.error(error_msg)
                            logger.error("Troubleshooting steps:")
                            logger.error(f"  1. Use a port >= 1024 (current: {config.http_transport.http_port})")
                            logger.error("  2. Run with appropriate privileges if using privileged ports")
                            raise OSError(f"Permission denied for port {config.http_transport.http_port}") from os_error
                        elif "Cannot assign requested address" in str(os_error):
                            error_msg = f"HTTP server startup failed: Cannot bind to address {config.http_transport.http_host}"
                            logger.error(error_msg)
                            logger.error("Troubleshooting steps:")
                            logger.error(f"  1. Verify the host address is valid: {config.http_transport.http_host}")
                            logger.error("  2. Use '0.0.0.0' to bind to all interfaces or '127.0.0.1' for localhost only")
                            logger.error("  3. Check network interface configuration")
                            raise OSError(f"Cannot bind to address {config.http_transport.http_host}") from os_error
                        else:
                            # Generic OS error
                            error_msg = f"HTTP server startup failed with OS error: {str(os_error)}"
                            logger.error(error_msg)
                            raise OSError(error_msg) from os_error
                    
                    except Exception as startup_error:
                        # Handle other startup errors
                        error_msg = f"HTTP server startup failed: {str(startup_error)}"
                        logger.error(error_msg)
                        logger.error("Check server configuration and system resources")
                        raise Exception(error_msg) from startup_error
            else:
                # Default transport (stdio) initialization
                logger.info("Initializing default transport (stdio)...")
                
                # Log default transport startup
                with logfire.span("mcp_server_startup", transport_mode="stdio"):
                    logger.info("Starting MCP server with stdio transport...")
                    
                    # Run with default transport (stdio)
                    try:
                        mcp_server.run()
                    except Exception as startup_error:
                        error_msg = f"MCP server startup failed: {str(startup_error)}"
                        logger.error(error_msg)
                        raise Exception(error_msg) from startup_error
                    
        except OSError as e:
            # Enhanced error handling for HTTP server startup failures
            error_context = {
                "transport_mode": config.transport_mode,
                "error_type": "server_startup_error",
                "error_details": str(e)
            }
            
            if config.transport_mode == "http":
                error_context.update({
                    "http_host": config.http_transport.http_host,
                    "http_port": config.http_transport.http_port,
                    "max_connections": config.http_transport.max_concurrent_connections,
                    "connection_timeout": config.http_transport.connection_timeout
                })
                
                # Log specific HTTP server startup failure
                logfire.error(
                    f"HTTP server startup failed: {str(e)}",
                    **error_context
                )
            else:
                # Log stdio transport startup failure
                logfire.error(
                    f"MCP server startup failed: {str(e)}",
                    **error_context
                )
            
            # Re-raise with context
            raise
            
        except ValueError as e:
            # Handle configuration validation errors
            error_context = {
                "transport_mode": config.transport_mode,
                "error_type": "configuration_error",
                "error_details": str(e)
            }
            
            if config.transport_mode == "http":
                error_context.update({
                    "http_host": config.http_transport.http_host,
                    "http_port": config.http_transport.http_port
                })
            
            logger.error(f"Configuration validation failed: {str(e)}")
            
            logfire.error(
                f"Server configuration validation failed: {str(e)}",
                **error_context
            )
            
            # Re-raise with context
            raise
            
        except Exception as e:
            # Handle any other unexpected startup errors
            error_context = {
                "transport_mode": config.transport_mode,
                "error_type": "unexpected_startup_error",
                "error_details": str(e)
            }
            
            if config.transport_mode == "http":
                error_context.update({
                    "http_host": config.http_transport.http_host,
                    "http_port": config.http_transport.http_port
                })
            
            logger.error(f"Unexpected server startup error: {str(e)}")
            
            logfire.error(
                f"Unexpected server startup error: {str(e)}",
                **error_context
            )
            
            # Re-raise with context
            raise
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt (SIGINT), shutting down...")
        logfire.info("Server shutdown initiated", reason="keyboard_interrupt")
    except SystemExit as e:
        logger.info(f"Received system exit signal (code: {e.code}), shutting down...")
        logfire.info("Server shutdown initiated", reason="system_exit", exit_code=e.code)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        logfire.error("Server startup failed", error=str(e), error_type=type(e).__name__)
        
        # For container environments, exit with non-zero code on startup failure
        sys.exit(1)
    finally:
        # Ensure cleanup happens with appropriate timeout for containers
        if orchestrator:
            logger.info("Cleaning up resources...")
            try:
                # Use shorter timeout for container environments
                shutdown_timeout = 25  # Leave 5 seconds buffer before container force-kill (usually 30s)
                asyncio.run(shutdown_components(orchestrator, timeout=shutdown_timeout))
                logger.info("✓ Cleanup completed")
                logfire.info("Server cleanup completed successfully")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
                logfire.error("Server cleanup failed", error=str(e))
                
                # For container environments, still exit cleanly even if cleanup fails
                # This prevents the container from hanging
                sys.exit(1)
        
        logger.info("Server shutdown complete")
        logfire.info("Server shutdown sequence completed")


if __name__ == "__main__":
    main()
