#!/usr/bin/env python3
"""
Docker health check script for RAG MCP Server.

This script performs a basic health check to ensure the server is running
and responding correctly. It's used by Docker's HEALTHCHECK instruction.
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, '/app')

try:
    from app.config import ServerConfig
    from app.orchestrator import Orchestrator
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    sys.exit(1)


async def check_health():
    """
    Perform health check on the RAG MCP Server.
    
    Returns:
        bool: True if healthy, False otherwise
    """
    try:
        # Load configuration
        config = ServerConfig()
        
        # Create orchestrator instance
        orchestrator = Orchestrator(config)
        
        # Perform basic health check
        health_status = await orchestrator.health_check()
        
        # Check if critical components are healthy
        critical_components = ['qdrant']
        for component in critical_components:
            if health_status.get(component) != 'ok':
                print(f"Health check failed: {component} is not healthy ({health_status.get(component)})")
                return False
        
        print("Health check passed: All critical components are healthy")
        return True
        
    except Exception as e:
        print(f"Health check failed with exception: {str(e)}")
        return False
    finally:
        # Clean up orchestrator if it was created
        try:
            if 'orchestrator' in locals():
                await orchestrator.close()
        except Exception as e:
            print(f"Warning: Failed to close orchestrator during health check: {e}")


def main():
    """Main entry point for health check."""
    try:
        # Run the async health check
        is_healthy = asyncio.run(check_health())
        
        if is_healthy:
            print("Docker health check: HEALTHY")
            sys.exit(0)
        else:
            print("Docker health check: UNHEALTHY")
            sys.exit(1)
            
    except Exception as e:
        print(f"Docker health check failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()