#!/usr/bin/env python3
"""
Simple Python MCP Client for RAG MCP Server

This script demonstrates how to connect to and interact with the RAG MCP Server
using HTTP transport.
"""

import requests
import json
import sys
import time
from typing import Dict, Any, Optional


class RAGMCPClient:
    """Simple MCP client for the RAG MCP Server."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the MCP client.
        
        Args:
            base_url: Base URL of the RAG MCP Server
        """
        self.base_url = base_url.rstrip('/')
        self.mcp_url = f"{self.base_url}/mcp/"
        self.health_url = f"{self.base_url}/health"
        self.request_id = 1
        self.timeout = 30
    
    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an MCP JSON-RPC request.
        
        Args:
            method: MCP method name
            params: Method parameters
            
        Returns:
            JSON-RPC response
            
        Raises:
            Exception: If request fails
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        self.request_id += 1
        
        try:
            response = requests.post(
                self.mcp_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Check for JSON-RPC errors
            if "error" in result:
                error = result["error"]
                raise Exception(f"MCP Error {error.get('code', 'UNKNOWN')}: {error.get('message', 'Unknown error')}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"HTTP request failed: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get server status.
        
        Returns:
            Server status information
        """
        response = self._make_request("tools/call", {
            "name": "get_server_status",
            "arguments": {}
        })
        return response.get("result", {})
    
    def ingest_csv(self, file_path: str) -> Dict[str, Any]:
        """
        Ingest a CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            Ingestion result
        """
        response = self._make_request("tools/call", {
            "name": "ingest_csv",
            "arguments": {"file_path": file_path}
        })
        return response.get("result", {})
    
    def query_documents(self, query: str, max_results: int = 10, 
                       score_threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Query documents.
        
        Args:
            query: Natural language query
            max_results: Maximum number of results
            score_threshold: Minimum similarity score
            
        Returns:
            Query results
        """
        args = {"query": query, "max_results": max_results}
        if score_threshold is not None:
            args["score_threshold"] = score_threshold
        
        response = self._make_request("tools/call", {
            "name": "query_documents",
            "arguments": args
        })
        return response.get("result", [])
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get health status via HTTP endpoint.
        
        Returns:
            Health status information
        """
        try:
            response = requests.get(self.health_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Health check failed: {e}")
    
    def test_connection(self) -> bool:
        """
        Test connection to the server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test health endpoint
            health = self.get_health()
            print(f"✓ Health check passed: {health.get('status')}")
            
            # Test MCP endpoint
            status = self.get_server_status()
            print(f"✓ MCP connection successful: {status.get('server_name')} v{status.get('version')}")
            print(f"  Status: {status.get('status')}")
            print(f"  Components: {status.get('components')}")
            
            return True
            
        except Exception as e:
            print(f"✗ Connection test failed: {e}")
            return False


def main():
    """Main function demonstrating client usage."""
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        server_url = "http://localhost:8000"
    
    print(f"Connecting to RAG MCP Server at: {server_url}")
    print("=" * 50)
    
    # Create client
    client = RAGMCPClient(server_url)
    
    # Test connection
    if not client.test_connection():
        print("\nConnection test failed. Please check:")
        print("1. Server is running with HTTP transport enabled")
        print("2. Server URL is correct")
        print("3. Network connectivity")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("Connection successful! You can now use the client.")
    print("=" * 50)
    
    # Interactive mode
    while True:
        print("\nAvailable commands:")
        print("1. status - Get server status")
        print("2. health - Get health status")
        print("3. ingest <file_path> - Ingest CSV file")
        print("4. query <query_text> - Query documents")
        print("5. quit - Exit")
        
        try:
            command = input("\nEnter command: ").strip().split()
            
            if not command:
                continue
            
            cmd = command[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "status":
                status = client.get_server_status()
                print(json.dumps(status, indent=2))
            elif cmd == "health":
                health = client.get_health()
                print(json.dumps(health, indent=2))
            elif cmd == "ingest":
                if len(command) < 2:
                    print("Usage: ingest <file_path>")
                    continue
                file_path = " ".join(command[1:])
                print(f"Ingesting CSV file: {file_path}")
                result = client.ingest_csv(file_path)
                print(json.dumps(result, indent=2))
            elif cmd == "query":
                if len(command) < 2:
                    print("Usage: query <query_text>")
                    continue
                query_text = " ".join(command[1:])
                print(f"Querying documents: {query_text}")
                results = client.query_documents(query_text)
                print(json.dumps(results, indent=2))
            else:
                print(f"Unknown command: {cmd}")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()