#!/usr/bin/env python3
"""
Docker health check script for RAG MCP Server.

This script provides a robust health check for containerized deployments,
supporting both HTTP transport and default transport modes.
"""

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Any


def check_http_health(host: str, port: int, health_path: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Check HTTP transport health via the health endpoint.
    
    Args:
        host: HTTP server host
        port: HTTP server port  
        health_path: Health check endpoint path
        timeout: Request timeout in seconds
        
    Returns:
        Health check result dictionary
    """
    try:
        # Construct health check URL
        if host == "0.0.0.0":
            # Use localhost for health checks when binding to all interfaces
            host = "127.0.0.1"
        
        url = f"http://{host}:{port}{health_path}"
        
        # Make health check request
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Docker-HealthCheck/1.0')
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                # Parse response body
                try:
                    health_data = json.loads(response.read().decode('utf-8'))
                    return {
                        "status": "healthy",
                        "transport": "http",
                        "url": url,
                        "response_code": response.status,
                        "health_data": health_data
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "unhealthy",
                        "transport": "http", 
                        "url": url,
                        "response_code": response.status,
                        "error": "Invalid JSON response from health endpoint"
                    }
            else:
                return {
                    "status": "unhealthy",
                    "transport": "http",
                    "url": url,
                    "response_code": response.status,
                    "error": f"Health endpoint returned status {response.status}"
                }
                
    except urllib.error.HTTPError as e:
        return {
            "status": "unhealthy",
            "transport": "http",
            "url": url,
            "response_code": e.code,
            "error": f"HTTP error: {e.code} {e.reason}"
        }
    except urllib.error.URLError as e:
        return {
            "status": "unhealthy", 
            "transport": "http",
            "url": url,
            "error": f"Connection error: {str(e.reason)}"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "transport": "http",
            "url": url,
            "error": f"Unexpected error: {str(e)}"
        }


def check_default_transport_health() -> Dict[str, Any]:
    """
    Check default transport (stdio) health by verifying process is running.
    
    For stdio transport, we can only do basic process health checks since
    there's no network endpoint to query.
    
    Returns:
        Health check result dictionary
    """
    try:
        # Basic Python import test to verify the application can start
        import app.main
        return {
            "status": "healthy",
            "transport": "default",
            "check_type": "process_health",
            "message": "Application modules can be imported successfully"
        }
    except ImportError as e:
        return {
            "status": "unhealthy",
            "transport": "default", 
            "check_type": "process_health",
            "error": f"Failed to import application: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "transport": "default",
            "check_type": "process_health", 
            "error": f"Unexpected error during health check: {str(e)}"
        }


def main():
    """
    Main health check function for Docker containers.
    
    This function determines the transport mode from environment variables
    and performs the appropriate health check.
    
    Exit codes:
        0: Healthy
        1: Unhealthy
    """
    # Get configuration from environment variables
    transport_mode = os.getenv("TRANSPORT_MODE", "default").lower()
    
    print(f"Docker health check starting (transport: {transport_mode})")
    
    if transport_mode == "http":
        # HTTP transport health check
        http_host = os.getenv("HTTP_HOST", "127.0.0.1")
        http_port = int(os.getenv("HTTP_PORT", "8000"))
        health_path = os.getenv("HEALTH_CHECK_PATH", "/health")
        
        print(f"Checking HTTP health at {http_host}:{http_port}{health_path}")
        
        result = check_http_health(http_host, http_port, health_path)
        
        print(f"Health check result: {json.dumps(result, indent=2)}")
        
        if result["status"] == "healthy":
            print("✓ HTTP transport health check passed")
            sys.exit(0)
        else:
            print("✗ HTTP transport health check failed")
            sys.exit(1)
            
    else:
        # Default transport (stdio) health check
        print("Checking default transport health")
        
        result = check_default_transport_health()
        
        print(f"Health check result: {json.dumps(result, indent=2)}")
        
        if result["status"] == "healthy":
            print("✓ Default transport health check passed")
            sys.exit(0)
        else:
            print("✗ Default transport health check failed")
            sys.exit(1)


if __name__ == "__main__":
    main()