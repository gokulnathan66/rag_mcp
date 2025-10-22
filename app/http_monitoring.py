"""
HTTP Transport Monitoring and Metrics for MCP Server.

This module provides:
- HTTP connection tracking and metrics collection
- Request/response monitoring with Logfire integration
- HTTP-specific error tracking and logging
- Connection lifecycle management
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict, deque

import logfire
from pydantic import BaseModel


logger = logging.getLogger(__name__)


@dataclass
class HTTPConnectionInfo:
    """Information about an active HTTP connection."""
    
    connection_id: str
    client_ip: str
    user_agent: Optional[str]
    connected_at: datetime
    last_activity: datetime
    request_count: int = 0
    total_response_time: float = 0.0
    error_count: int = 0


class HTTPMetrics(BaseModel):
    """HTTP transport metrics collection."""
    
    # Connection metrics
    total_connections: int = 0
    active_connections: int = 0
    peak_connections: int = 0
    connection_utilization: float = 0.0  # Percentage of max connections used
    
    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    requests_per_second: float = 0.0
    
    # Response time metrics
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p95_response_time: float = 0.0  # 95th percentile response time
    p99_response_time: float = 0.0  # 99th percentile response time
    
    # Error metrics
    total_errors: int = 0
    error_rate: float = 0.0  # Percentage of failed requests
    error_rate_per_second: float = 0.0
    
    # HTTP status code breakdown
    status_2xx: int = 0  # Success responses
    status_3xx: int = 0  # Redirection responses
    status_4xx: int = 0  # Client error responses
    status_5xx: int = 0  # Server error responses
    
    # Transport-specific metrics
    mcp_tool_requests: int = 0  # Requests to MCP tools
    health_check_requests: int = 0  # Health check requests
    cors_preflight_requests: int = 0  # CORS preflight requests
    
    # Bandwidth metrics
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    avg_request_size: float = 0.0
    avg_response_size: float = 0.0
    
    # Timestamp and uptime
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    monitoring_start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0


class HTTPMonitor:
    """
    HTTP transport monitoring and metrics collection.
    
    This class provides comprehensive monitoring for HTTP transport including:
    - Connection tracking and lifecycle management
    - Request/response metrics collection
    - Error tracking and categorization
    - Logfire integration for structured monitoring
    """
    
    def __init__(self, max_response_time_samples: int = 1000, max_connections: int = 100):
        """
        Initialize HTTP monitor.
        
        Args:
            max_response_time_samples: Maximum number of response time samples to keep
            max_connections: Maximum number of concurrent connections (for utilization calculation)
        """
        self.active_connections: Dict[str, HTTPConnectionInfo] = {}
        self.connection_lock = asyncio.Lock()
        self.max_connections = max_connections
        
        # Metrics tracking
        self.total_connections = 0
        self.peak_connections = 0
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_errors = 0
        
        # HTTP status code tracking
        self.status_2xx = 0
        self.status_3xx = 0
        self.status_4xx = 0
        self.status_5xx = 0
        
        # Request type tracking
        self.mcp_tool_requests = 0
        self.health_check_requests = 0
        self.cors_preflight_requests = 0
        
        # Bandwidth tracking
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.request_sizes = deque(maxlen=max_response_time_samples)
        self.response_sizes = deque(maxlen=max_response_time_samples)
        
        # Response time tracking (using deque for efficient operations)
        self.response_times = deque(maxlen=max_response_time_samples)
        
        # Error categorization and rate tracking
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_timestamps = deque(maxlen=1000)  # Track error timestamps for rate calculation
        self.request_timestamps = deque(maxlen=1000)  # Track request timestamps for RPS calculation
        
        # Start time for uptime calculation
        self.start_time = datetime.now(timezone.utc)
        
        logger.info(f"HTTP monitor initialized with max_connections: {max_connections}")
        
        # Log initialization with Logfire
        logfire.info(
            "HTTP monitor initialized",
            monitor_type="http_transport",
            max_response_time_samples=max_response_time_samples,
            max_connections=max_connections,
            start_time=self.start_time.isoformat()
        )
    
    async def register_connection(
        self,
        connection_id: Optional[str] = None,
        client_ip: str = "unknown",
        user_agent: Optional[str] = None
    ) -> str:
        """
        Register a new HTTP connection.
        
        Args:
            connection_id: Optional connection ID (generated if not provided)
            client_ip: Client IP address
            user_agent: Client user agent string
            
        Returns:
            Connection ID for tracking
        """
        if connection_id is None:
            connection_id = str(uuid.uuid4())
        
        async with self.connection_lock:
            now = datetime.now(timezone.utc)
            
            connection_info = HTTPConnectionInfo(
                connection_id=connection_id,
                client_ip=client_ip,
                user_agent=user_agent,
                connected_at=now,
                last_activity=now
            )
            
            self.active_connections[connection_id] = connection_info
            self.total_connections += 1
            
            # Update peak connections
            current_active = len(self.active_connections)
            if current_active > self.peak_connections:
                self.peak_connections = current_active
            
            logger.info(
                f"HTTP connection registered: {connection_id} from {client_ip}"
            )
            
            # Log connection with Logfire
            logfire.info(
                "HTTP connection registered",
                connection_id=connection_id,
                client_ip=client_ip,
                user_agent=user_agent,
                active_connections=current_active,
                total_connections=self.total_connections,
                transport_type="http_mcp"
            )
            
            return connection_id
    
    async def unregister_connection(self, connection_id: str) -> None:
        """
        Unregister an HTTP connection.
        
        Args:
            connection_id: Connection ID to unregister
        """
        async with self.connection_lock:
            connection_info = self.active_connections.pop(connection_id, None)
            
            if connection_info:
                # Calculate connection duration
                duration = (datetime.now(timezone.utc) - connection_info.connected_at).total_seconds()
                
                logger.info(
                    f"HTTP connection unregistered: {connection_id} "
                    f"(duration: {duration:.2f}s, requests: {connection_info.request_count})"
                )
                
                # Log disconnection with Logfire
                logfire.info(
                    "HTTP connection unregistered",
                    connection_id=connection_id,
                    client_ip=connection_info.client_ip,
                    duration_seconds=duration,
                    request_count=connection_info.request_count,
                    error_count=connection_info.error_count,
                    avg_response_time=connection_info.total_response_time / max(connection_info.request_count, 1),
                    active_connections=len(self.active_connections),
                    transport_type="http_mcp"
                )
            else:
                logger.warning(f"Attempted to unregister unknown connection: {connection_id}")
    
    async def record_request_start(
        self,
        connection_id: str,
        method: str,
        path: str,
        correlation_id: Optional[str] = None,
        request_size: Optional[int] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Record the start of an HTTP request.
        
        Args:
            connection_id: Connection ID
            method: HTTP method
            path: Request path
            correlation_id: Optional correlation ID for tracking
            request_size: Optional request size in bytes
            user_agent: Optional user agent string
            
        Returns:
            Request tracking ID
        """
        request_id = correlation_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        async with self.connection_lock:
            # Update connection activity
            if connection_id in self.active_connections:
                self.active_connections[connection_id].last_activity = now
                self.active_connections[connection_id].request_count += 1
            
            self.total_requests += 1
            
            # Track request timestamp for RPS calculation
            self.request_timestamps.append(now.timestamp())
            
            # Track request size if provided
            if request_size is not None:
                self.total_bytes_received += request_size
                self.request_sizes.append(request_size)
            
            # Categorize request type based on path
            if path.startswith('/mcp/'):
                self.mcp_tool_requests += 1
            elif path in ['/health', '/healthz', '/health-check']:
                self.health_check_requests += 1
            elif method == 'OPTIONS':
                self.cors_preflight_requests += 1
            
            logger.debug(
                f"HTTP request started: {method} {path} "
                f"(connection: {connection_id}, request: {request_id})"
            )
            
            # Log request start with Logfire
            logfire.info(
                "HTTP request started",
                request_id=request_id,
                connection_id=connection_id,
                method=method,
                path=path,
                request_size=request_size,
                user_agent=user_agent,
                total_requests=self.total_requests,
                transport_type="http_mcp"
            )
            
            return request_id
    
    async def record_request_complete(
        self,
        connection_id: str,
        request_id: str,
        status_code: int,
        response_time: float,
        error: Optional[str] = None,
        response_size: Optional[int] = None
    ) -> None:
        """
        Record the completion of an HTTP request.
        
        Args:
            connection_id: Connection ID
            request_id: Request tracking ID
            status_code: HTTP status code
            response_time: Request response time in seconds
            error: Optional error message if request failed
            response_size: Optional response size in bytes
        """
        now = datetime.now(timezone.utc)
        
        async with self.connection_lock:
            # Update connection metrics
            if connection_id in self.active_connections:
                conn_info = self.active_connections[connection_id]
                conn_info.last_activity = now
                conn_info.total_response_time += response_time
                
                if error:
                    conn_info.error_count += 1
            
            # Update global metrics
            self.response_times.append(response_time)
            
            # Track response size if provided
            if response_size is not None:
                self.total_bytes_sent += response_size
                self.response_sizes.append(response_size)
            
            # Update status code counters
            if 200 <= status_code < 300:
                self.status_2xx += 1
            elif 300 <= status_code < 400:
                self.status_3xx += 1
            elif 400 <= status_code < 500:
                self.status_4xx += 1
            elif 500 <= status_code < 600:
                self.status_5xx += 1
            
            # Update success/failure metrics
            if error or status_code >= 400:
                self.failed_requests += 1
                if error:
                    self.error_counts[error] += 1
                    self.total_errors += 1
                    # Track error timestamp for rate calculation
                    self.error_timestamps.append(now.timestamp())
            else:
                self.successful_requests += 1
            
            # Determine log level based on status
            if status_code >= 500:
                log_level = "error"
            elif status_code >= 400:
                log_level = "warning"
            else:
                log_level = "info"
            
            logger.log(
                getattr(logging, log_level.upper()),
                f"HTTP request completed: {status_code} "
                f"(request: {request_id}, response_time: {response_time:.3f}s)"
            )
            
            # Log request completion with Logfire
            logfire_method = getattr(logfire, log_level)
            logfire_method(
                "HTTP request completed",
                request_id=request_id,
                connection_id=connection_id,
                status_code=status_code,
                response_time_seconds=response_time,
                response_size=response_size,
                error=error,
                successful_requests=self.successful_requests,
                failed_requests=self.failed_requests,
                status_2xx=self.status_2xx,
                status_4xx=self.status_4xx,
                status_5xx=self.status_5xx,
                transport_type="http_mcp"
            )
    
    async def record_error(
        self,
        error_type: str,
        error_message: str,
        connection_id: Optional[str] = None,
        request_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an HTTP transport error.
        
        Args:
            error_type: Type/category of error
            error_message: Error message
            connection_id: Optional connection ID
            request_id: Optional request ID
            context: Optional additional context
        """
        async with self.connection_lock:
            self.error_counts[error_type] += 1
            self.total_errors += 1
            
            # Update connection error count if applicable
            if connection_id and connection_id in self.active_connections:
                self.active_connections[connection_id].error_count += 1
        
        error_context = {
            "error_type": error_type,
            "error_message": error_message,
            "total_errors": self.total_errors,
            "transport_type": "http_mcp"
        }
        
        if connection_id:
            error_context["connection_id"] = connection_id
        if request_id:
            error_context["request_id"] = request_id
        if context:
            error_context.update(context)
        
        logger.error(f"HTTP transport error: {error_type} - {error_message}")
        
        # Log error with Logfire
        logfire.error(
            "HTTP transport error",
            **error_context
        )
    
    async def get_metrics(self) -> HTTPMetrics:
        """
        Get current HTTP transport metrics.
        
        Returns:
            HTTPMetrics object with current statistics
        """
        now = datetime.now(timezone.utc)
        
        async with self.connection_lock:
            # Calculate response time statistics
            if self.response_times:
                sorted_times = sorted(self.response_times)
                avg_response_time = sum(sorted_times) / len(sorted_times)
                min_response_time = sorted_times[0]
                max_response_time = sorted_times[-1]
                
                # Calculate percentiles
                p95_index = int(0.95 * len(sorted_times))
                p99_index = int(0.99 * len(sorted_times))
                p95_response_time = sorted_times[min(p95_index, len(sorted_times) - 1)]
                p99_response_time = sorted_times[min(p99_index, len(sorted_times) - 1)]
            else:
                avg_response_time = min_response_time = max_response_time = 0.0
                p95_response_time = p99_response_time = 0.0
            
            # Calculate rates (requests and errors per second over last minute)
            one_minute_ago = now.timestamp() - 60
            recent_requests = sum(1 for ts in self.request_timestamps if ts > one_minute_ago)
            recent_errors = sum(1 for ts in self.error_timestamps if ts > one_minute_ago)
            
            requests_per_second = recent_requests / 60.0
            error_rate_per_second = recent_errors / 60.0
            
            # Calculate error rate percentage
            error_rate = (self.failed_requests / max(self.total_requests, 1)) * 100
            
            # Calculate connection utilization
            connection_utilization = (len(self.active_connections) / max(self.max_connections, 1)) * 100
            
            # Calculate average request/response sizes
            avg_request_size = sum(self.request_sizes) / len(self.request_sizes) if self.request_sizes else 0.0
            avg_response_size = sum(self.response_sizes) / len(self.response_sizes) if self.response_sizes else 0.0
            
            # Calculate uptime
            uptime_seconds = (now - self.start_time).total_seconds()
            
            metrics = HTTPMetrics(
                # Connection metrics
                total_connections=self.total_connections,
                active_connections=len(self.active_connections),
                peak_connections=self.peak_connections,
                connection_utilization=connection_utilization,
                
                # Request metrics
                total_requests=self.total_requests,
                successful_requests=self.successful_requests,
                failed_requests=self.failed_requests,
                requests_per_second=requests_per_second,
                
                # Response time metrics
                avg_response_time=avg_response_time,
                min_response_time=min_response_time,
                max_response_time=max_response_time,
                p95_response_time=p95_response_time,
                p99_response_time=p99_response_time,
                
                # Error metrics
                total_errors=self.total_errors,
                error_rate=error_rate,
                error_rate_per_second=error_rate_per_second,
                
                # HTTP status code breakdown
                status_2xx=self.status_2xx,
                status_3xx=self.status_3xx,
                status_4xx=self.status_4xx,
                status_5xx=self.status_5xx,
                
                # Transport-specific metrics
                mcp_tool_requests=self.mcp_tool_requests,
                health_check_requests=self.health_check_requests,
                cors_preflight_requests=self.cors_preflight_requests,
                
                # Bandwidth metrics
                total_bytes_sent=self.total_bytes_sent,
                total_bytes_received=self.total_bytes_received,
                avg_request_size=avg_request_size,
                avg_response_size=avg_response_size,
                
                # Timestamp and uptime
                last_updated=now,
                monitoring_start_time=self.start_time,
                uptime_seconds=uptime_seconds
            )
            
            return metrics
    
    async def get_connection_info(self, connection_id: str) -> Optional[HTTPConnectionInfo]:
        """
        Get information about a specific connection.
        
        Args:
            connection_id: Connection ID to look up
            
        Returns:
            HTTPConnectionInfo if connection exists, None otherwise
        """
        async with self.connection_lock:
            return self.active_connections.get(connection_id)
    
    async def get_active_connections(self) -> List[HTTPConnectionInfo]:
        """
        Get information about all active connections.
        
        Returns:
            List of HTTPConnectionInfo for all active connections
        """
        async with self.connection_lock:
            return list(self.active_connections.values())
    
    async def cleanup_stale_connections(self, timeout_seconds: int = 300) -> int:
        """
        Clean up stale connections that haven't been active recently.
        
        Args:
            timeout_seconds: Timeout in seconds for considering a connection stale
            
        Returns:
            Number of connections cleaned up
        """
        now = datetime.now(timezone.utc)
        stale_connections = []
        
        async with self.connection_lock:
            for conn_id, conn_info in self.active_connections.items():
                if (now - conn_info.last_activity).total_seconds() > timeout_seconds:
                    stale_connections.append(conn_id)
            
            # Remove stale connections
            for conn_id in stale_connections:
                conn_info = self.active_connections.pop(conn_id)
                logger.warning(
                    f"Cleaned up stale connection: {conn_id} "
                    f"(last activity: {conn_info.last_activity})"
                )
                
                # Log cleanup with Logfire
                logfire.warning(
                    "Stale HTTP connection cleaned up",
                    connection_id=conn_id,
                    client_ip=conn_info.client_ip,
                    last_activity=conn_info.last_activity.isoformat(),
                    stale_duration_seconds=(now - conn_info.last_activity).total_seconds(),
                    transport_type="http_mcp"
                )
        
        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale HTTP connections")
        
        return len(stale_connections)
    
    async def get_error_breakdown(self) -> Dict[str, Any]:
        """
        Get detailed error breakdown and analysis.
        
        Returns:
            Dictionary with error analysis information
        """
        async with self.connection_lock:
            total_errors = sum(self.error_counts.values())
            
            # Calculate error percentages
            error_breakdown = {}
            for error_type, count in self.error_counts.items():
                error_breakdown[error_type] = {
                    "count": count,
                    "percentage": (count / max(total_errors, 1)) * 100
                }
            
            # Recent error rate (last 5 minutes)
            five_minutes_ago = datetime.now(timezone.utc).timestamp() - 300
            recent_errors = sum(1 for ts in self.error_timestamps if ts > five_minutes_ago)
            recent_error_rate = recent_errors / 300.0  # Errors per second
            
            return {
                "total_errors": total_errors,
                "error_types": error_breakdown,
                "recent_error_rate_per_second": recent_error_rate,
                "most_common_error": max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None
            }
    
    async def get_performance_analysis(self) -> Dict[str, Any]:
        """
        Get performance analysis and recommendations.
        
        Returns:
            Dictionary with performance analysis
        """
        metrics = await self.get_metrics()
        
        # Performance indicators
        performance_issues = []
        recommendations = []
        
        # Check response time performance
        if metrics.avg_response_time > 2.0:
            performance_issues.append("High average response time")
            recommendations.append("Consider optimizing request processing or scaling resources")
        
        if metrics.p95_response_time > 5.0:
            performance_issues.append("High 95th percentile response time")
            recommendations.append("Investigate slow requests and optimize bottlenecks")
        
        # Check error rates
        if metrics.error_rate > 5.0:
            performance_issues.append("High error rate")
            recommendations.append("Investigate and fix sources of errors")
        
        # Check connection utilization
        if metrics.connection_utilization > 80.0:
            performance_issues.append("High connection utilization")
            recommendations.append("Consider increasing max_concurrent_connections or scaling")
        
        # Check request rate
        if metrics.requests_per_second > 50.0:  # Arbitrary threshold
            performance_issues.append("High request rate")
            recommendations.append("Monitor system resources and consider load balancing")
        
        return {
            "performance_score": max(0, 100 - len(performance_issues) * 20),  # Simple scoring
            "issues": performance_issues,
            "recommendations": recommendations,
            "key_metrics": {
                "avg_response_time": metrics.avg_response_time,
                "p95_response_time": metrics.p95_response_time,
                "error_rate": metrics.error_rate,
                "connection_utilization": metrics.connection_utilization,
                "requests_per_second": metrics.requests_per_second
            }
        }
    
    async def get_traffic_analysis(self) -> Dict[str, Any]:
        """
        Get traffic pattern analysis.
        
        Returns:
            Dictionary with traffic analysis
        """
        metrics = await self.get_metrics()
        
        # Request type distribution
        total_categorized = metrics.mcp_tool_requests + metrics.health_check_requests + metrics.cors_preflight_requests
        other_requests = max(0, metrics.total_requests - total_categorized)
        
        request_distribution = {
            "mcp_tools": {
                "count": metrics.mcp_tool_requests,
                "percentage": (metrics.mcp_tool_requests / max(metrics.total_requests, 1)) * 100
            },
            "health_checks": {
                "count": metrics.health_check_requests,
                "percentage": (metrics.health_check_requests / max(metrics.total_requests, 1)) * 100
            },
            "cors_preflight": {
                "count": metrics.cors_preflight_requests,
                "percentage": (metrics.cors_preflight_requests / max(metrics.total_requests, 1)) * 100
            },
            "other": {
                "count": other_requests,
                "percentage": (other_requests / max(metrics.total_requests, 1)) * 100
            }
        }
        
        # Status code distribution
        total_responses = metrics.status_2xx + metrics.status_3xx + metrics.status_4xx + metrics.status_5xx
        status_distribution = {
            "2xx_success": {
                "count": metrics.status_2xx,
                "percentage": (metrics.status_2xx / max(total_responses, 1)) * 100
            },
            "3xx_redirect": {
                "count": metrics.status_3xx,
                "percentage": (metrics.status_3xx / max(total_responses, 1)) * 100
            },
            "4xx_client_error": {
                "count": metrics.status_4xx,
                "percentage": (metrics.status_4xx / max(total_responses, 1)) * 100
            },
            "5xx_server_error": {
                "count": metrics.status_5xx,
                "percentage": (metrics.status_5xx / max(total_responses, 1)) * 100
            }
        }
        
        return {
            "request_types": request_distribution,
            "status_codes": status_distribution,
            "bandwidth": {
                "total_bytes_sent": metrics.total_bytes_sent,
                "total_bytes_received": metrics.total_bytes_received,
                "avg_request_size": metrics.avg_request_size,
                "avg_response_size": metrics.avg_response_size
            }
        }
    
    async def log_periodic_metrics(self) -> None:
        """Log periodic metrics summary for monitoring."""
        metrics = await self.get_metrics()
        
        logger.info(
            f"HTTP Transport Metrics - "
            f"Active: {metrics.active_connections}/{self.max_connections} ({metrics.connection_utilization:.1f}%), "
            f"RPS: {metrics.requests_per_second:.1f}, "
            f"Success Rate: {((metrics.successful_requests / max(metrics.total_requests, 1)) * 100):.1f}%, "
            f"Avg Response: {metrics.avg_response_time:.3f}s, "
            f"P95: {metrics.p95_response_time:.3f}s"
        )
        
        # Log comprehensive metrics with Logfire
        logfire.info(
            "HTTP transport periodic metrics",
            # Connection metrics
            active_connections=metrics.active_connections,
            total_connections=metrics.total_connections,
            peak_connections=metrics.peak_connections,
            connection_utilization=metrics.connection_utilization,
            
            # Request metrics
            total_requests=metrics.total_requests,
            successful_requests=metrics.successful_requests,
            failed_requests=metrics.failed_requests,
            requests_per_second=metrics.requests_per_second,
            
            # Response time metrics
            avg_response_time_seconds=metrics.avg_response_time,
            min_response_time_seconds=metrics.min_response_time,
            max_response_time_seconds=metrics.max_response_time,
            p95_response_time_seconds=metrics.p95_response_time,
            p99_response_time_seconds=metrics.p99_response_time,
            
            # Error metrics
            total_errors=metrics.total_errors,
            error_rate_percent=metrics.error_rate,
            error_rate_per_second=metrics.error_rate_per_second,
            
            # Status code breakdown
            status_2xx=metrics.status_2xx,
            status_3xx=metrics.status_3xx,
            status_4xx=metrics.status_4xx,
            status_5xx=metrics.status_5xx,
            
            # Request type breakdown
            mcp_tool_requests=metrics.mcp_tool_requests,
            health_check_requests=metrics.health_check_requests,
            cors_preflight_requests=metrics.cors_preflight_requests,
            
            # Bandwidth metrics
            total_bytes_sent=metrics.total_bytes_sent,
            total_bytes_received=metrics.total_bytes_received,
            avg_request_size=metrics.avg_request_size,
            avg_response_size=metrics.avg_response_size,
            
            # Uptime
            uptime_seconds=metrics.uptime_seconds,
            
            transport_type="http_mcp"
        )
    
    async def log_error_rate_alert(self, threshold: float = 10.0) -> None:
        """
        Log alert if error rate exceeds threshold.
        
        Args:
            threshold: Error rate threshold percentage for alerting
        """
        metrics = await self.get_metrics()
        
        if metrics.error_rate > threshold:
            error_breakdown = await self.get_error_breakdown()
            
            logger.warning(
                f"HTTP error rate alert: {metrics.error_rate:.1f}% exceeds threshold {threshold}% "
                f"(recent rate: {metrics.error_rate_per_second:.2f} errors/sec)"
            )
            
            logfire.warning(
                "HTTP error rate alert",
                error_rate_percent=metrics.error_rate,
                threshold_percent=threshold,
                error_rate_per_second=metrics.error_rate_per_second,
                total_errors=metrics.total_errors,
                most_common_error=error_breakdown.get("most_common_error"),
                component="http_monitor_alert"
            )
    
    async def log_performance_alert(self, response_time_threshold: float = 5.0) -> None:
        """
        Log alert if performance degrades.
        
        Args:
            response_time_threshold: Response time threshold in seconds for alerting
        """
        metrics = await self.get_metrics()
        
        if metrics.p95_response_time > response_time_threshold:
            logger.warning(
                f"HTTP performance alert: P95 response time {metrics.p95_response_time:.3f}s "
                f"exceeds threshold {response_time_threshold}s "
                f"(avg: {metrics.avg_response_time:.3f}s)"
            )
            
            logfire.warning(
                "HTTP performance alert",
                p95_response_time_seconds=metrics.p95_response_time,
                threshold_seconds=response_time_threshold,
                avg_response_time_seconds=metrics.avg_response_time,
                requests_per_second=metrics.requests_per_second,
                connection_utilization=metrics.connection_utilization,
                component="http_monitor_alert"
            )


# Global HTTP monitor instance
_http_monitor: Optional[HTTPMonitor] = None


def get_http_monitor() -> Optional[HTTPMonitor]:
    """Get the global HTTP monitor instance."""
    return _http_monitor


def initialize_http_monitor(
    max_response_time_samples: int = 1000,
    max_connections: int = 100
) -> HTTPMonitor:
    """
    Initialize the global HTTP monitor instance.
    
    Args:
        max_response_time_samples: Maximum number of response time samples to keep
        max_connections: Maximum number of concurrent connections
        
    Returns:
        HTTPMonitor instance
    """
    global _http_monitor
    if _http_monitor is None:
        _http_monitor = HTTPMonitor(max_response_time_samples, max_connections)
        logger.info("Global HTTP monitor initialized")
    return _http_monitor


def shutdown_http_monitor() -> None:
    """Shutdown the global HTTP monitor instance."""
    global _http_monitor
    if _http_monitor is not None:
        logger.info("Shutting down HTTP monitor")
        _http_monitor = None