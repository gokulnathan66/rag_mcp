#!/usr/bin/env python3
"""
Simple MCP client to test the RAG MCP server query functionality.
This client properly handles FastMCP's Server-Sent Events (SSE) protocol.
"""

import asyncio
import json
import aiohttp
from typing import Dict, Any, List


class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = None
        self.initialized = False
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def send_request(self, method: str, params: Dict[str, Any] = None, request_id: str = "1") -> Dict[str, Any]:
        """Send an MCP request to the server using FastMCP's SSE protocol."""
        if params is None:
            params = {}
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        async with self.session.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        ) as response:
            # FastMCP uses Server-Sent Events
            text = await response.text()
            
            # Parse SSE format - look for data: lines
            lines = text.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    json_data = line[6:]  # Remove 'data: ' prefix
                    try:
                        result = json.loads(json_data)
                        return result
                    except json.JSONDecodeError:
                        continue
            
            # If no valid JSON found, return error
            return {"error": {"code": -32000, "message": "No valid JSON in SSE response"}}
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP session."""
        result = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {
                    "listChanged": True
                },
                "sampling": {}
            },
            "clientInfo": {
                "name": "test-mcp-client",
                "version": "1.0.0"
            }
        })
        
        if "error" not in result:
            self.initialized = True
        
        return result
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        if not self.initialized:
            return {"error": {"code": -32000, "message": "Client not initialized"}}
        return await self.send_request("tools/list")
    
    async def query_documents(self, query: str, max_results: int = 10, score_threshold: float = None) -> Dict[str, Any]:
        """Query documents using the RAG MCP server."""
        if not self.initialized:
            return {"error": {"code": -32000, "message": "Client not initialized"}}
            
        params = {
            "name": "query_documents",
            "arguments": {
                "query": query,
                "max_results": max_results
            }
        }
        
        if score_threshold is not None:
            params["arguments"]["score_threshold"] = score_threshold
        
        return await self.send_request("tools/call", params)
    
    async def get_server_status(self) -> Dict[str, Any]:
        """Get server status."""
        if not self.initialized:
            return {"error": {"code": -32000, "message": "Client not initialized"}}
            
        return await self.send_request("tools/call", {
            "name": "get_server_status",
            "arguments": {}
        })


async def main():
    """Main function to test the MCP client."""
    print("🔍 Testing RAG MCP Server Query Functionality")
    print("=" * 60)
    
    async with MCPClient() as client:
        try:
            # Initialize the session
            print("1. Initializing MCP session...")
            init_result = await client.initialize()
            if "error" in init_result:
                print(f"❌ Initialization failed: {init_result['error']}")
                return
            print("✅ Session initialized successfully")
            
            # List available tools
            print("\n2. Listing available tools...")
            tools_result = await client.list_tools()
            if "error" in tools_result:
                print(f"❌ Failed to list tools: {tools_result['error']}")
                return
            
            tools = tools_result.get("result", {}).get("tools", [])
            print(f"✅ Available tools: {[tool['name'] for tool in tools]}")
            
            # Get server status
            print("\n3. Checking server status...")
            status_result = await client.get_server_status()
            if "error" in status_result:
                print(f"❌ Failed to get server status: {status_result['error']}")
            else:
                status = status_result.get("result", {})
                print(f"✅ Server status: {status.get('status', 'unknown')}")
                print(f"   Components: {status.get('components', {})}")
            
            # Query documents
            print("\n4. Querying documents...")
            query = "i love lunch"
            max_results = 5
            
            print(f"   Query: '{query}'")
            print(f"   Max results: {max_results}")
            
            query_result = await client.query_documents(
                query=query,
                max_results=max_results
            )
            
            if "error" in query_result:
                print(f"❌ Query failed: {query_result['error']}")
                return
            
            # Process and display results
            results = query_result.get("result", [])
            print(f"\n✅ Query completed successfully!")
            print(f"📊 Found {len(results)} results:")
            print("-" * 60)
            
            if not results:
                print("   No documents found matching your query.")
                print("   This might be because:")
                print("   - No CSV files have been uploaded yet")
                print("   - The query doesn't match any indexed content")
                print("   - The vector database is empty")
            else:
                for i, result in enumerate(results, 1):
                    print(f"\n📄 Result {i}:")
                    print(f"   Score: {result.get('score', 'N/A'):.4f}")
                    print(f"   Content: {result.get('content', 'N/A')[:200]}...")
                    if result.get('metadata'):
                        print(f"   Metadata: {result.get('metadata')}")
            
        except Exception as e:
            print(f"❌ Error occurred: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())