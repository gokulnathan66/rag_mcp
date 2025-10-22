"""
HTTP Connection Manager for MCP Server.

This module provides:
- HTTP connection tracking and session management
- Connection limit enforcement and timeout handling
- Connection cleanup and resource management
- Integration with HTTP monitoring and metrics
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
from contextlib import asynccontextmanager

import logfire
from pydantic import BaseModel

from .config import HTTPTransportConfig
from .http_monitoring import HTTPMonitor, get_http_monitor
from .errors import RAGError


logger = logging.getLogger(__name__)


class ConnectionLimitExceeded(RAGError):
    """Raised when connection limit is exceeded."""
    
    def __init__(self, current_connections: int, max_connections: int, correlation_id: Optional[str] = None):
        super().__init__(
            code="CONNECTION_LIMIT_EXCEEDED",
            message=f"Connection limit exceeded: {current_connections}/{max_connections}",
            details={
                "current_connections": current_connections,
                "max_connections": max_connections,
                "error_type": "connection_limit"
            },
            retry_after=30,
            correlation_id=correlation_id
        )


class ConnectionTimeout(RAGError):
    """Raised when connection timeout occurs."""
    
    def __init__(self, connection_id: str, timeout_seconds: int, correlation_id: Optional[str] = None):
        super().__init__(
            code="CONNECTION_TIMEOUT",
            message=f"Connection {connection_id} timed out after {timeout_seconds} seconds",
            details={
                "connection_id": connection_id,
                "timeout_seconds": timeout_seconds,
                "error_type": "connection_timeout"
            },
            correlation_id=correlation_id
        )


@dataclass
class ConnectionSession:
    """Represents an active HTTP connection session."""
    
    connection_id: str
    client_ip: str
    user_agent: Optional[str]
    created_at: datetime
    last_activity: datetime
    request_count: int = 0
    active_requests: Set[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.active_requests is None:
            self.active_requests = set()
        if self.metadata is None:
            self.metadata = {}
    
    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
    
    def add_request(self, request_id: str) -> None:
        """Add an active request to this session."""
        self.active_requests.add(request_id)
        self.request_count += 1
        self.update_activity()
    
    def remove_request(self, request_id: str) -> None:
        """Remove an active request from this session."""
        self.active_requests.discard(request_id)
        self.update_activity()
    
    def is_idle(self) -> bool:
        """Check if the connection has no active requests."""
        return len(self.active_requests) == 0
    
    def get_session_duration(self) -> float:
        """Get the total session duration in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()
    
    def get_idle_time(self) -> float:
        """Get the time since last activity in seconds."""
        return (datetime.now(timezone.utc) - self.last_activity).total_seconds()


class HTTPConnectionManager:
    """
    Manages HTTP connections for the MCP server.
    
    This class provides:
    - Connection tracking and session management
    - Connection limit enforcement
    - Timeout handling and cleanup
    - Resource management and monitoring integration
    """
    
    def __init__(self, config: HTTPTransportConfig, http_monitor: Optional[HTTPMonitor] = None):
        """
        Initialize the HTTP connection manager.
        
        Args:
            config: HTTP transport configuration
            http_monitor: Optional HTTP monitor for metrics collection
        """
        self.config = config
        self.http_monitor = http_monitor or get_http_monitor()
        
        # Connection tracking
        self.active_sessions: Dict[str, ConnectionSession] = {}
        self.connection_lock = asyncio.Lock()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Statistics
        self.total_connections = 0
        self.rejected_connections = 0
        self.timed_out_connections = 0
        
        logger.info(
            f"HTTP connection manager initialized - "
            f"max_connections: {config.max_concurrent_connections}, "
            f"timeout: {config.connection_timeout}s"
        )
        
        # Log initialization with Logfire
        logfire.info(
            "HTTP connection manager initialized",
            max_concurrent_connections=config.max_concurrent_connections,
            connection_timeout=config.connection_timeout,
            request_timeout=config.request_timeout,
            component="http_connection_manager"
        )
    
    async def start(self) -> None:
        """Start the connection manager and cleanup tasks."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("HTTP connection manager started")
            
            logfire.info(
                "HTTP connection manager started",
                component="http_connection_manager"
            )
    
    async def stop(self) -> None:
        """Stop the connection manager and cleanup tasks."""
        self._shutdown_event.set()
        
        if self._cleanup_task:
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Cleanup task did not complete within timeout, cancelling")
                self._cleanup_task.cancel()
            
            self._cleanup_task = None
        
        # Close all active sessions
        async with self.connection_lock:
            session_count = len(self.active_sessions)
            for session in list(self.active_sessions.values()):
                await self._close_session(session, reason="server_shutdown")
        
        logger.info(f"HTTP connection manager stopped - closed {session_count} active sessions")
        
        logfire.info(
            "HTTP connection manager stopped",
            closed_sessions=session_count,
            component="http_connection_manager"
        )
    
    @asynccontextmanager
    async def create_connection(
        self,
        client_ip: str,
        user_agent: Optional[str] = None,
        connection_id: Optional[str] = None
    ):
        """
        Create and manage an HTTP connection session.
        
        Args:
            client_ip: Client IP address
            user_agent: Client user agent string
            connection_id: Optional connection ID (generated if not provided)
            
        Yields:
            ConnectionSession object for the active connection
            
        Raises:
            ConnectionLimitExceeded: If connection limit is exceeded
        """
        if connection_id is None:
            connection_id = str(uuid.uuid4())
        
        # Check connection limits
        async with self.connection_lock:
            current_connections = len(self.active_sessions)
            if current_connections >= self.config.max_concurrent_connections:
                self.rejected_connections += 1
                
                logger.warning(
                    f"Connection limit exceeded: {current_connections}/{self.config.max_concurrent_connections} "
                    f"(client: {client_ip})"
                )
                
                logfire.warning(
                    "HTTP connection rejected - limit exceeded",
                    client_ip=client_ip,
                    current_connections=current_connections,
                    max_connections=self.config.max_concurrent_connections,
                    rejected_connections=self.rejected_connections,
                    component="http_connection_manager"
                )
                
                raise ConnectionLimitExceeded(
                    current_connections=current_connections,
                    max_connections=self.config.max_concurrent_connections,
                    correlation_id=connection_id
                )
        
        # Create session
        session = await self._create_session(connection_id, client_ip, user_agent)
        
        try:
            yield session
        finally:
            # Cleanup session
            await self._close_session(session, reason="connection_closed")
    
    async def _create_session(
        self,
        connection_id: str,
        client_ip: str,
        user_agent: Optional[str]
    ) -> ConnectionSession:
        """Create a new connection session."""
        now = datetime.now(timezone.utc)
        
        session = ConnectionSession(
            connection_id=connection_id,
            client_ip=client_ip,
            user_agent=user_agent,
            created_at=now,
            last_activity=now
        )
        
        async with self.connection_lock:
            self.active_sessions[connection_id] = session
            self.total_connections += 1
        
        # Register with HTTP monitor if available
        if self.http_monitor:
            await self.http_monitor.register_connection(
                connection_id=connection_id,
                client_ip=client_ip,
                user_agent=user_agent
            )
        
        logger.info(
            f"HTTP connection created: {connection_id} from {client_ip} "
            f"(active: {len(self.active_sessions)})"
        )
        
        logfire.info(
            "HTTP connection created",
            connection_id=connection_id,
            client_ip=client_ip,
            user_agent=user_agent,
            active_connections=len(self.active_sessions),
            total_connections=self.total_connections,
            component="http_connection_manager"
        )
        
        return session
    
    async def _close_session(self, session: ConnectionSession, reason: str = "unknown") -> None:
        """Close a connection session and cleanup resources."""
        async with self.connection_lock:
            if session.connection_id in self.active_sessions:
                del self.active_sessions[session.connection_id]
        
        # Unregister from HTTP monitor if available
        if self.http_monitor:
            await self.http_monitor.unregister_connection(session.connection_id)
        
        session_duration = session.get_session_duration()
        
        logger.info(
            f"HTTP connection closed: {session.connection_id} "
            f"(reason: {reason}, duration: {session_duration:.2f}s, requests: {session.request_count})"
        )
        
        logfire.info(
            "HTTP connection closed",
            connection_id=session.connection_id,
            client_ip=session.client_ip,
            reason=reason,
            duration_seconds=session_duration,
            request_count=session.request_count,
            active_connections=len(self.active_sessions),
            component="http_connection_manager"
        )
    
    async def get_session(self, connection_id: str) -> Optional[ConnectionSession]:
        """Get a connection session by ID."""
        async with self.connection_lock:
            return self.active_sessions.get(connection_id)
    
    async def add_request(self, connection_id: str, request_id: str) -> bool:
        """
        Add a request to a connection session.
        
        Args:
            connection_id: Connection ID
            request_id: Request ID
            
        Returns:
            True if request was added, False if connection not found
        """
        async with self.connection_lock:
            session = self.active_sessions.get(connection_id)
            if session:
                session.add_request(request_id)
                return True
            return False
    
    async def remove_request(self, connection_id: str, request_id: str) -> bool:
        """
        Remove a request from a connection session.
        
        Args:
            connection_id: Connection ID
            request_id: Request ID
            
        Returns:
            True if request was removed, False if connection not found
        """
        async with self.connection_lock:
            session = self.active_sessions.get(connection_id)
            if session:
                session.remove_request(request_id)
                return True
            return False
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics."""
        async with self.connection_lock:
            active_count = len(self.active_sessions)
            idle_count = sum(1 for session in self.active_sessions.values() if session.is_idle())
            
            # Calculate average session duration for active sessions
            if self.active_sessions:
                avg_duration = sum(
                    session.get_session_duration() 
                    for session in self.active_sessions.values()
                ) / len(self.active_sessions)
            else:
                avg_duration = 0.0
            
            return {
                "active_connections": active_count,
                "idle_connections": idle_count,
                "busy_connections": active_count - idle_count,
                "total_connections": self.total_connections,
                "rejected_connections": self.rejected_connections,
                "timed_out_connections": self.timed_out_connections,
                "max_connections": self.config.max_concurrent_connections,
                "connection_utilization": (active_count / self.config.max_concurrent_connections) * 100,
                "average_session_duration": avg_duration
            }
    
    async def get_active_sessions(self) -> List[ConnectionSession]:
        """Get a list of all active connection sessions."""
        async with self.connection_lock:
            return list(self.active_sessions.values())
    
    async def enforce_limits(self) -> bool:
        """
        Check and enforce connection limits.
        
        Returns:
            True if within limits, False if limits exceeded
        """
        async with self.connection_lock:
            current_connections = len(self.active_sessions)
            return current_connections < self.config.max_concurrent_connections
    
    async def cleanup_stale_connections(self) -> int:
        """
        Clean up stale connections that have exceeded timeout.
        
        Returns:
            Number of connections cleaned up
        """
        now = datetime.now(timezone.utc)
        stale_sessions = []
        
        async with self.connection_lock:
            for session in self.active_sessions.values():
                # Check for connection timeout
                if session.get_idle_time() > self.config.connection_timeout:
                    stale_sessions.append(session)
        
        # Close stale sessions
        cleanup_count = 0
        for session in stale_sessions:
            await self._close_session(session, reason="timeout")
            self.timed_out_connections += 1
            cleanup_count += 1
            
            logger.warning(
                f"Connection timed out: {session.connection_id} "
                f"(idle: {session.get_idle_time():.1f}s)"
            )
            
            logfire.warning(
                "HTTP connection timed out",
                connection_id=session.connection_id,
                client_ip=session.client_ip,
                idle_time_seconds=session.get_idle_time(),
                timeout_seconds=self.config.connection_timeout,
                component="http_connection_manager"
            )
        
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} stale HTTP connections")
        
        return cleanup_count
    
    async def _cleanup_loop(self) -> None:
        """Background task for periodic connection cleanup."""
        logger.info("HTTP connection cleanup loop started")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Wait for cleanup interval or shutdown
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=60.0  # Cleanup every minute
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    # Perform cleanup
                    cleanup_count = await self.cleanup_stale_connections()
                    
                    # Log periodic statistics
                    stats = await self.get_connection_stats()
                    logger.debug(
                        f"Connection stats - Active: {stats['active_connections']}, "
                        f"Idle: {stats['idle_connections']}, "
                        f"Utilization: {stats['connection_utilization']:.1f}%"
                    )
                    
        except Exception as e:
            logger.error(f"Error in connection cleanup loop: {e}", exc_info=True)
            
            logfire.error(
                "HTTP connection cleanup loop error",
                error=str(e),
                component="http_connection_manager"
            )
        
        logger.info("HTTP connection cleanup loop stopped")


# Global connection manager instance
_connection_manager: Optional[HTTPConnectionManager] = None


def get_connection_manager() -> Optional[HTTPConnectionManager]:
    """Get the global HTTP connection manager instance."""
    return _connection_manager


def initialize_connection_manager(
    config: HTTPTransportConfig,
    http_monitor: Optional[HTTPMonitor] = None
) -> HTTPConnectionManager:
    """
    Initialize the global HTTP connection manager.
    
    Args:
        config: HTTP transport configuration
        http_monitor: Optional HTTP monitor instance
        
    Returns:
        HTTPConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = HTTPConnectionManager(config, http_monitor)
        logger.info("Global HTTP connection manager initialized")
    return _connection_manager


async def shutdown_connection_manager() -> None:
    """Shutdown the global HTTP connection manager."""
    global _connection_manager
    if _connection_manager is not None:
        await _connection_manager.stop()
        _connection_manager = None
        logger.info("Global HTTP connection manager shutdown")