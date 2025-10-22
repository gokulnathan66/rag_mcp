"""
Standalone web server for the RAG MCP Server UI.

This module provides a separate web server that can run alongside
the MCP server to provide a web interface for CSV upload and querying.
"""

import asyncio
import logging
from pathlib import Path

import uvicorn
from app.config import ServerConfig
from app.orchestrator import Orchestrator
from app.web_api import create_web_api


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def initialize_orchestrator(config: ServerConfig) -> Orchestrator:
    """Initialize the orchestrator and ensure Qdrant collection exists."""
    logger.info("Initializing orchestrator...")
    orchestrator = Orchestrator(config)
    
    # Ensure Qdrant collection exists
    await orchestrator.qdrant_client.ensure_collection(
        collection_name=config.qdrant_collection_name,
        vector_size=384  # Default for all-MiniLM-L6-v2
    )
    
    logger.info("Orchestrator initialized successfully")
    return orchestrator


def main():
    """Main entry point for the web server."""
    # Load configuration
    config = ServerConfig()
    
    logger.info("=" * 60)
    logger.info("Starting RAG MCP Server Web UI")
    logger.info("=" * 60)
    logger.info(f"Configuration:")
    logger.info(f"  CSV directory: {config.csv_data_directory}")
    logger.info(f"  Qdrant URL: {config.qdrant_url}")
    logger.info(f"  Qdrant collection: {config.qdrant_collection_name}")
    logger.info("=" * 60)
    
    # Initialize orchestrator
    orchestrator = asyncio.run(initialize_orchestrator(config))
    
    # Create web API
    app = create_web_api(orchestrator, config)
    
    # Run server
    logger.info("Starting web server on http://0.0.0.0:2332")
    logger.info("Open http://localhost:2332 in your browser")
    logger.info("=" * 60)
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=2332,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Shutting down web server...")
    finally:
        asyncio.run(orchestrator.close())
        logger.info("Web server stopped")


if __name__ == "__main__":
    main()
