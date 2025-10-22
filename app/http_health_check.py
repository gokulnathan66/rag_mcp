"""
HTTP Health Check Endpoint for MCP Server.

This module provides:
- HTTP health check endpoint implementation
- Integration with existing get_server_status tool
- HTTP-specific health check response format
- Configurable health check path and options
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Literal

import logfire
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .config import HTTPTransportConfig
from .models import ServerStatus
from .http_connection_manager import HTTPConnectionManager, get_connection_manager
from .http_monitoring import HTTPMonitor, get_http_monitor


logger = logging.getLogger(__name__)


class HTTPHealthStatus(BaseModel):
    """HTTP health check response model."""
    
    status: Literal["healthy", "unhealthy", "degraded"]
    timestamp: datetime
    version: str
    uptime_seconds: Optional[float] = None
    components: Dict[str, str]
    http_transport: Dict[str, Any]
    error: Optional[str] = None


class HTTPHealthChecker:
    """
    HTTP health check implementation for MCP server.
    
    This class provides health check functionality specifically designed
    for HTTP transport, integrating with existing server status tools
    and HTTP-specific monitoring.
    """
    
    def __init__(
        self,
        config: HTTPTransportConfig,
        get_server_status_func,
        connection_manager: Optional[HTTPConnectionManager] = None,
        http_monitor: Optional[HTTPMonitor] = None
    ):
        """
        Initialize HTTP health checker.
        
        Args:
            config: HTTP transport configuration
            get_server_status_func: Function to get server status (from MCP tools)
            connection_manager: Optional HTTP connection manager
            http_monitor: Optional HTTP monitor
        """
        self.config = config
        self.get_server_status_func = get_server_status_func
        self.connection_manager = connection_manager or get_connection_manager()
        self.http_monitor = http_monitor or get_http_monitor()
        
        logger.info(
            f"HTTP health checker initialized - "
            f"endpoint: {config.health_check_path}, "
            f"enabled: {config.enable_health_endpoint}"
        )
        
        logfire.info(
            "HTTP health checker initialized",
            health_check_path=config.health_check_path,
            enabled=config.enable_health_endpoint,
            component="http_health_checker"
        )
    
    async def check_health(self) -> HTTPHealthStatus:
        """
        Perform comprehensive health check for HTTP transport.
        
        Returns:
            HTTPHealthStatus with detailed health information
        """
        correlation_id = f"health_check_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        with logfire.span(
            "http_health_check",
            correlation_id=correlation_id,
            component="http_health_checker"
        ):
            try:
                # Get base server status from existing MCP tool
                server_status: ServerStatus = await self.get_server_status_func()
                
                # Get HTTP transport specific metrics
                http_transport_info = await self._get_http_transport_info()
                
                # Determine overall health status
                overall_status = self._determine_health_status(server_status, http_transport_info)
                
                health_response = HTTPHealthStatus(
                    status=overall_status,
                    timestamp=datetime.now(timezone.utc),
                    version=server_status.version,
                    uptime_seconds=server_status.uptime_seconds,
                    components=server_status.components,
                    http_transport=http_transport_info
                )
                
                logger.debug(
                    f"Health check completed: {overall_status} "
                    f"(components: {len(server_status.components)}, "
                    f"active_connections: {http_transport_info.get('active_connections', 0)})"
                )
                
                logfire.info(
                    "HTTP health check completed",
                    status=overall_status,
                    uptime_seconds=server_status.uptime_seconds,
                    active_connections=http_transport_info.get('active_connections', 0),
                    component_count=len(server_status.components),
                    correlation_id=correlation_id,
                    component="http_health_checker"
                )
                
                return health_response
                
            except Exception as e:
                error_msg = f"Health check failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                
                logfire.error(
                    "HTTP health check failed",
                    error=str(e),
                    correlation_id=correlation_id,
                    component="http_health_checker"
                )
                
                # Return unhealthy status with error information
                return HTTPHealthStatus(
                    status="unhealthy",
                    timestamp=datetime.now(timezone.utc),
                    version="unknown",
                    components={},
                    http_transport={"status": "error", "error": str(e)},
                    error=error_msg
                )
    
    async def _get_http_transport_info(self) -> Dict[str, Any]:
        """Get HTTP transport specific health information."""
        transport_info = {
            "transport_mode": "http",
            "host": self.config.http_host,
            "port": self.config.http_port,
            "max_connections": self.config.max_concurrent_connections,
            "connection_timeout": self.config.connection_timeout,
            "cors_enabled": self.config.enable_cors
        }
        
        # Add connection manager statistics if available
        if self.connection_manager:
            try:
                conn_stats = await self.connection_manager.get_connection_stats()
                transport_info.update({
                    "active_connections": conn_stats["active_connections"],
                    "idle_connections": conn_stats["idle_connections"],
                    "total_connections": conn_stats["total_connections"],
                    "rejected_connections": conn_stats["rejected_connections"],
                    "connection_utilization": conn_stats["connection_utilization"]
                })
            except Exception as e:
                logger.warning(f"Failed to get connection stats: {e}")
                transport_info["connection_stats_error"] = str(e)
        
        # Add HTTP monitor metrics if available
        if self.http_monitor:
            try:
                http_metrics = await self.http_monitor.get_metrics()
                transport_info.update({
                    "total_requests": http_metrics.total_requests,
                    "successful_requests": http_metrics.successful_requests,
                    "failed_requests": http_metrics.failed_requests,
                    "avg_response_time": http_metrics.avg_response_time,
                    "error_rate": http_metrics.error_rate
                })
            except Exception as e:
                logger.warning(f"Failed to get HTTP metrics: {e}")
                transport_info["http_metrics_error"] = str(e)
        
        return transport_info
    
    def _determine_health_status(
        self,
        server_status: ServerStatus,
        http_transport_info: Dict[str, Any]
    ) -> Literal["healthy", "unhealthy", "degraded"]:
        """
        Determine overall health status based on server and HTTP transport status.
        
        Args:
            server_status: Base server status from MCP tool
            http_transport_info: HTTP transport specific information
            
        Returns:
            Overall health status
        """
        # Check base server status
        if server_status.status == "error":
            return "unhealthy"
        
        # Check critical components
        critical_components = ["qdrant_client"]
        for component in critical_components:
            if server_status.components.get(component) == "error":
                return "unhealthy"
        
        # Check HTTP transport specific issues
        if "connection_stats_error" in http_transport_info or "http_metrics_error" in http_transport_info:
            return "degraded"
        
        # Check connection utilization
        connection_utilization = http_transport_info.get("connection_utilization", 0)
        if connection_utilization > 90:  # Over 90% utilization
            return "degraded"
        
        # Check error rate
        error_rate = http_transport_info.get("error_rate", 0)
        if error_rate > 10:  # Over 10% error rate
            return "degraded"
        
        # Check if any non-critical components have issues
        non_critical_issues = any(
            status not in ["ok", "unknown"] 
            for component, status in server_status.components.items()
            if component not in critical_components
        )
        
        if non_critical_issues:
            return "degraded"
        
        return "healthy"


def setup_health_check_endpoint(
    app: FastAPI,
    config: HTTPTransportConfig,
    get_server_status_func,
    connection_manager: Optional[HTTPConnectionManager] = None,
    http_monitor: Optional[HTTPMonitor] = None
) -> HTTPHealthChecker:
    """
    Set up HTTP health check endpoint on FastAPI app.
    
    Args:
        app: FastAPI application instance
        config: HTTP transport configuration
        get_server_status_func: Function to get server status
        connection_manager: Optional HTTP connection manager
        http_monitor: Optional HTTP monitor
        
    Returns:
        HTTPHealthChecker instance
    """
    if not config.enable_health_endpoint:
        logger.info("Health check endpoint disabled in configuration")
        return None
    
    health_checker = HTTPHealthChecker(
        config=config,
        get_server_status_func=get_server_status_func,
        connection_manager=connection_manager,
        http_monitor=http_monitor
    )
    
    @app.get(config.health_check_path)
    async def health_check():
        """
        HTTP health check endpoint for load balancer integration.
        
        Returns comprehensive health status including:
        - Overall server status
        - Component health status
        - HTTP transport metrics
        - Connection statistics
        """
        try:
            health_status = await health_checker.check_health()
            
            # Return appropriate HTTP status code based on health
            if health_status.status == "healthy":
                status_code = 200
            elif health_status.status == "degraded":
                status_code = 200  # Still operational but with issues
            else:  # unhealthy
                status_code = 503  # Service Unavailable
            
            return JSONResponse(
                status_code=status_code,
                content=health_status.dict()
            )
            
        except Exception as e:
            logger.error(f"Health check endpoint error: {e}", exc_info=True)
            
            logfire.error(
                "Health check endpoint error",
                error=str(e),
                component="http_health_checker"
            )
            
            # Return error response
            error_response = {
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health check failed: {str(e)}",
                "components": {},
                "http_transport": {"status": "error"}
            }
            
            return JSONResponse(
                status_code=503,
                content=error_response
            )
    
    logger.info(f"Health check endpoint configured at {config.health_check_path}")
    
    logfire.info(
        "Health check endpoint configured",
        path=config.health_check_path,
        component="http_health_checker"
    )
    
    return health_checker


def create_standalone_health_check_response(
    server_name: str,
    version: str,
    status: Literal["healthy", "unhealthy", "degraded"] = "healthy",
    components: Optional[Dict[str, str]] = None,
    uptime_seconds: Optional[float] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standalone health check response without dependencies.
    
    This function can be used when the full health check system is not available
    but a basic health response is needed.
    
    Args:
        server_name: Name of the server
        version: Server version
        status: Health status
        components: Optional component status dict
        uptime_seconds: Optional uptime in seconds
        error: Optional error message
        
    Returns:
        Health check response dictionary
    """
    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server_name": server_name,
        "version": version,
        "uptime_seconds": uptime_seconds,
        "components": components or {},
        "http_transport": {
            "transport_mode": "http",
            "status": "ok" if status != "unhealthy" else "error"
        },
        "error": error
    }


# Health check utilities for testing and monitoring
async def perform_health_check_test(
    health_checker: HTTPHealthChecker,
    expected_status: Optional[str] = None
) -> bool:
    """
    Perform a health check test and validate the result.
    
    Args:
        health_checker: HTTPHealthChecker instance
        expected_status: Optional expected status for validation
        
    Returns:
        True if health check passed, False otherwise
    """
    try:
        health_status = await health_checker.check_health()
        
        # Basic validation
        if not health_status.status:
            logger.error("Health check returned no status")
            return False
        
        if health_status.status not in ["healthy", "unhealthy", "degraded"]:
            logger.error(f"Health check returned invalid status: {health_status.status}")
            return False
        
        # Optional status validation
        if expected_status and health_status.status != expected_status:
            logger.warning(
                f"Health check status mismatch: expected {expected_status}, "
                f"got {health_status.status}"
            )
            return False
        
        logger.info(f"Health check test passed: {health_status.status}")
        return True
        
    except Exception as e:
        logger.error(f"Health check test failed: {e}", exc_info=True)
        return False