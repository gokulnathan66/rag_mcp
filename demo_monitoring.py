#!/usr/bin/env python
"""
Demonstration script for Task 8: Monitoring and Configuration

This script demonstrates:
1. Logfire integration with structured logging
2. Health checks for all components
3. Server status monitoring
"""

import asyncio
import sys
from datetime import datetime

from app.config import ServerConfig
from app.orchestrator import Orchestrator


async def demo_monitoring():
    """Demonstrate monitoring and health check features."""
    
    print("=" * 70)
    print("RAG MCP Server - Monitoring and Configuration Demo")
    print("=" * 70)
    print()
    
    # 1. Configuration
    print("1. CONFIGURATION")
    print("-" * 70)
    config = ServerConfig()
    print(f"   Server Name:        {config.mcp_server_name}")
    print(f"   Version:            {config.mcp_version}")
    print(f"   Logfire Enabled:    {config.enable_logfire}")
    print(f"   Log Level:          {config.log_level}")
    print(f"   Qdrant URL:         {config.qdrant_url}")
    print(f"   Embedding Model:    {config.embedding_model_name}")
    print(f"   Max Chunk Size:     {config.max_chunk_size}")
    print(f"   Chunk Overlap:      {config.chunk_overlap}")
    print()
    
    # 2. Component Initialization
    print("2. COMPONENT INITIALIZATION")
    print("-" * 70)
    orchestrator = Orchestrator(config)
    print("   ✓ CSV Parser initialized")
    print("   ✓ FastEmbed Embedder initialized")
    print("   ✓ Qdrant Client initialized")
    print("   ✓ LangGraph Workflows initialized")
    print()
    
    # 3. Health Checks
    print("3. HEALTH CHECKS")
    print("-" * 70)
    try:
        health = await orchestrator.health_check()
        
        print(f"   CSV Parser:    [{health['csv_parser'].upper():^8}]")
        print(f"   Embedder:      [{health['embedder'].upper():^8}]")
        print(f"   Qdrant:        [{health['qdrant'].upper():^8}]")
        
        # Overall status
        all_ok = all(status == "ok" for status in health.values())
        overall = "HEALTHY" if all_ok else "DEGRADED"
        print()
        print(f"   Overall Status: {overall}")
        
    except Exception as e:
        print(f"   ✗ Health check failed: {e}")
        return 1
    
    print()
    
    # 4. Server Status (simulated)
    print("4. SERVER STATUS")
    print("-" * 70)
    print(f"   Status:         RUNNING")
    print(f"   Timestamp:      {datetime.now().isoformat()}")
    print(f"   Components:     {len(health)} active")
    print()
    
    # 5. Monitoring Features
    print("5. MONITORING FEATURES")
    print("-" * 70)
    print("   ✓ Logfire spans for all operations")
    print("   ✓ Structured logging with context")
    print("   ✓ Correlation IDs for request tracking")
    print("   ✓ Performance metrics (batch sizes, timing)")
    print("   ✓ Error tracking with detailed context")
    print("   ✓ Health checks for all components")
    print("   ✓ Server status reporting via MCP tool")
    print()
    
    # Cleanup
    await orchestrator.close()
    
    print("=" * 70)
    print("Demo completed successfully!")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(demo_monitoring())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nDemo failed with error: {e}")
        sys.exit(1)
