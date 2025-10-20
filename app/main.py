import asyncio
import logging
from typing import Any, Dict, List, Optional

import logfire
from fastmcp import FastMCP
from pydantic import BaseModel

from .config import ServerConfig
from .models import QueryResult, ErrorResponse, ServerStatus, IngestionStatus


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
            logger = logging.getLogger(__name__)
            logger.info(f"Logfire configured for {config.mcp_server_name} v{config.mcp_version}")
        except Exception as e:
            # Fallback to basic logging if logfire setup fails
            logging.basicConfig(level=getattr(logging, config.log_level.upper()))
            logger = logging.getLogger(__name__)
            logger.warning(f"Logfire setup failed, using basic logging: {e}")
    else:
        # Set up basic logging when logfire is disabled
        logging.basicConfig(level=getattr(logging, config.log_level.upper()))


# MCP Tool Input/Output Models
class QueryDocumentsInput(BaseModel):
    query: str
    max_results: int = 10


class IngestCollectionInput(BaseModel):
    collection_name: str
    filters: Optional[Dict[str, Any]] = None


# Import the models from models.py instead of redefining them


# Initialize FastMCP server
def create_mcp_server(config: ServerConfig) -> FastMCP:
    """Create and configure the FastMCP server with RAG tools."""
    
    # Set up Logfire monitoring
    setup_logfire(config)
    
    # Create FastMCP server instance
    mcp = FastMCP(config.mcp_server_name)
    
    @mcp.tool()
    async def query_documents(input_data: QueryDocumentsInput) -> List[QueryResult]:
        """Query documents using vector similarity search."""
        with logfire.span("query_documents", query=input_data.query, max_results=input_data.max_results):
            try:
                # TODO: Implement actual query logic in later tasks
                # This is a placeholder that will be replaced when orchestrator is implemented
                logfire.info(f"Querying documents with: {input_data.query}")
                return []
            except Exception as e:
                logfire.error(f"Error querying documents: {str(e)}")
                raise
    
    @mcp.tool()
    async def ingest_firestore_collection(input_data: IngestCollectionInput) -> IngestionStatus:
        """Ingest documents from a Firestore collection into the vector database."""
        with logfire.span("ingest_collection", collection=input_data.collection_name):
            try:
                # TODO: Implement actual ingestion logic in later tasks
                # This is a placeholder that will be replaced when orchestrator is implemented
                logfire.info(f"Ingesting collection: {input_data.collection_name}")
                return IngestionStatus(
                    status="success",
                    collection_name=input_data.collection_name,
                    documents_processed=0,
                    chunks_created=0,
                    embeddings_generated=0
                )
            except Exception as e:
                logfire.error(f"Error ingesting collection: {str(e)}")
                raise
    
    @mcp.tool()
    async def get_server_status() -> ServerStatus:
        """Get the current status of the RAG MCP server and its components."""
        with logfire.span("get_server_status"):
            try:
                logfire.info("Getting server status")
                return ServerStatus(
                    server_name=config.mcp_server_name,
                    version=config.mcp_version,
                    status="running",
                    components={
                        "firestore_client": "not_initialized",
                        "qdrant_client": "not_initialized", 
                        "fastembed": "not_initialized",
                        "langgraph": "not_initialized"
                    }
                )
            except Exception as e:
                logfire.error(f"Error getting server status: {str(e)}")
                raise
    
    return mcp


# Main application entry point
def main():
    """Main application entry point."""
    # Load configuration
    config = ServerConfig()
    
    # Create MCP server
    mcp_server = create_mcp_server(config)
    
    # Start the server (FastMCP handles the asyncio loop internally)
    mcp_server.run()


if __name__ == "__main__":
    main()
