#!/usr/bin/env python3
"""
Simple test to demonstrate RAG MCP server functionality.
This script uses a more direct approach to test the MCP tools.
"""

import asyncio
import json
import aiohttp
from typing import Dict, Any


async def test_mcp_server():
    """Test the MCP server functionality step by step."""
    print("🔍 Testing RAG MCP Server - Document Query")
    print("=" * 60)
    
    base_url = "http://localhost:8080"
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Initialize the session
        print("1. Initializing MCP session...")
        init_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "rag-test-client",
                    "version": "1.0.0"
                }
            },
            "id": "init"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        async with session.post(f"{base_url}/mcp", json=init_payload, headers=headers) as response:
            text = await response.text()
            print(f"   Response: {text[:100]}...")
            
            # Extract JSON from SSE format
            for line in text.split('\n'):
                if line.startswith('data: '):
                    try:
                        result = json.loads(line[6:])
                        if "error" in result:
                            print(f"❌ Initialization failed: {result['error']}")
                            return
                        print("✅ Session initialized successfully")
                        break
                    except json.JSONDecodeError:
                        continue
        
        # Step 2: First, let's ingest our sample data
        print("\n2. Ingesting sample CSV data...")
        ingest_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ingest_csv",
                "arguments": {
                    "file_path": "/app/data/sample_data.csv"
                }
            },
            "id": "ingest"
        }
        
        async with session.post(f"{base_url}/mcp", json=ingest_payload, headers=headers) as response:
            text = await response.text()
            print(f"   Response: {text[:200]}...")
            
            # Extract JSON from SSE format
            for line in text.split('\n'):
                if line.startswith('data: '):
                    try:
                        result = json.loads(line[6:])
                        if "error" in result:
                            print(f"❌ Ingestion failed: {result['error']}")
                            # Continue anyway - maybe data is already there
                            break
                        elif "result" in result:
                            ingestion_result = result["result"]
                            print(f"✅ Ingestion completed: {ingestion_result.get('status', 'unknown')}")
                            print(f"   Documents processed: {ingestion_result.get('documents_processed', 0)}")
                            print(f"   Chunks created: {ingestion_result.get('chunks_created', 0)}")
                            break
                    except json.JSONDecodeError:
                        continue
        
        # Step 3: Query for documents related to "i love lunch"
        print("\n3. Querying documents for 'i love lunch' (max 5 results)...")
        query_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_documents",
                "arguments": {
                    "query": "i love lunch",
                    "max_results": 5
                }
            },
            "id": "query"
        }
        
        async with session.post(f"{base_url}/mcp", json=query_payload, headers=headers) as response:
            text = await response.text()
            print(f"   Response: {text[:200]}...")
            
            # Extract JSON from SSE format
            for line in text.split('\n'):
                if line.startswith('data: '):
                    try:
                        result = json.loads(line[6:])
                        if "error" in result:
                            print(f"❌ Query failed: {result['error']}")
                            return
                        elif "result" in result:
                            query_results = result["result"]
                            print(f"\n✅ Query completed successfully!")
                            print(f"📊 Found {len(query_results)} results:")
                            print("-" * 60)
                            
                            if not query_results:
                                print("   No documents found matching your query.")
                            else:
                                for i, doc in enumerate(query_results, 1):
                                    print(f"\n📄 Result {i}:")
                                    print(f"   Score: {doc.get('score', 'N/A'):.4f}")
                                    print(f"   Content: {doc.get('content', 'N/A')[:150]}...")
                                    if doc.get('metadata'):
                                        print(f"   Metadata: {doc.get('metadata')}")
                            break
                    except json.JSONDecodeError:
                        continue
        
        # Step 4: Get server status
        print("\n4. Getting server status...")
        status_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_server_status",
                "arguments": {}
            },
            "id": "status"
        }
        
        async with session.post(f"{base_url}/mcp", json=status_payload, headers=headers) as response:
            text = await response.text()
            
            # Extract JSON from SSE format
            for line in text.split('\n'):
                if line.startswith('data: '):
                    try:
                        result = json.loads(line[6:])
                        if "error" in result:
                            print(f"❌ Status check failed: {result['error']}")
                        elif "result" in result:
                            status = result["result"]
                            print(f"✅ Server status: {status.get('status', 'unknown')}")
                            print(f"   Server: {status.get('server_name')} v{status.get('version')}")
                            print(f"   Uptime: {status.get('uptime_seconds', 0):.1f} seconds")
                            components = status.get('components', {})
                            print(f"   Components:")
                            for comp, stat in components.items():
                                print(f"     - {comp}: {stat}")
                        break
                    except json.JSONDecodeError:
                        continue


if __name__ == "__main__":
    asyncio.run(test_mcp_server())