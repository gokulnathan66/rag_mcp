"""
HTTP Error Handler and Middleware for MCP Server.

This module provides:
- HTTP error handling middleware for FastMCP
- Structured error response formatting
- HTTP status code mapping for MCP errors
- Request/response context tracking for errors
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Awaitable
from contextlib import asynccontextmanager

import logfire
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .errors import (
    RAGError, HTTPTransportError, HTTPConnectionError, HTTPRequestError,
    HTTPResponseError, HTTPServerError, handle_http_transport_error,
    create_http_error_response, map_error_to_http_status
)
from .models import HTTPErrorResponse, HTTPRequestContext, HTTPResponseContext
from .http_monitoring import get_http_monitor


logger = logging.getLogger(__name__)


class HTTPErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    HTTP error handling middleware for MCP server.
    
    This middleware provides:
    - Automatic error catching and formatting
    - HTTP status code mapping
    - Request/response context tracking
    - Integration with monitoring and logging
    """
    
    def __init__(
        self,
        app: ASGIApp,
        include_error_details: bool = True,
        log_errors: bool = True
    ):
        """
        Initialize HTTP error handler middleware.
        
        Args:
            app: ASGI application
            include_error_details: Whether to include detailed error information in responses
            log_errors: Whether to log errors automatically
        """
        super().__init__(app)
        self.include_error_details = include_error_details
        self.log_errors = log_errors
        
        logger.info(
            f"HTTP error handler middleware initialized - "
            f"include_details: {include_error_details}, log_errors: {log_errors}"
        )
        
        logfire.info(
            "HTTP error handler middleware initialized",
            include_error_details=include_error_details,
            log_errors=log_errors,
            component="http_error_handler"
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process HTTP request with error handling.
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response with error handling
        """
        # Generate request context
        request_context = self._create_request_context(request)
        start_time = time.time()
        
        # Add request context to request state for access by handlers
        request.state.http_context = request_context
        
        # Record request start with HTTP monitor
        http_monitor = get_http_monitor()
        if http_monitor:
            await http_monitor.record_request_start(
                connection_id=request_context.connection_id or "unknown",
                method=request_context.method,
                path=request_context.path,
                correlation_id=request_context.request_id
            )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate response time
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Record successful request completion
            if http_monitor:
                await http_monitor.record_request_complete(
                    connection_id=request_context.connection_id or "unknown",
                    request_id=request_context.request_id,
                    status_code=response.status_code,
                    response_time=response_time / 1000,  # Convert back to seconds
                    error=None
                )
            
            # Log successful request
            if self.log_errors:  # Use same flag for request logging
                logger.info(
                    f"HTTP request completed: {request_context.method} {request_context.path} "
                    f"-> {response.status_code} ({response_time:.1f}ms)"
                )
            
            return response
            
        except Exception as error:
            # Calculate response time for error case
            response_time = (time.time() - start_time) * 1000
            
            # Handle the error and create structured response
            error_response = await self._handle_error(
                error=error,
                request_context=request_context,
                response_time=response_time
            )
            
            # Record failed request completion
            if http_monitor:
                await http_monitor.record_request_complete(
                    connection_id=request_context.connection_id or "unknown",
                    request_id=request_context.request_id,
                    status_code=error_response["http_status_code"],
                    response_time=response_time / 1000,
                    error=error_response["error"]["code"]
                )
            
            return JSONResponse(
                status_code=error_response["http_status_code"],
                content=error_response
            )
    
    def _create_request_context(self, request: Request) -> HTTPRequestContext:
        """
        Create HTTP request context from FastAPI request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            HTTPRequestContext with request information
        """
        # Extract client IP (handle proxy headers)
        client_ip = None
        if hasattr(request, 'client') and request.client:
            client_ip = request.client.host
        
        # Check for forwarded headers (common in load balancer setups)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            client_ip = real_ip
        
        # Extract user agent
        user_agent = request.headers.get('User-Agent')
        
        # Generate or extract connection ID (if available from connection manager)
        connection_id = request.headers.get('X-Connection-ID')
        if not connection_id:
            connection_id = str(uuid.uuid4())
        
        return HTTPRequestContext(
            connection_id=connection_id,
            method=request.method,
            path=str(request.url.path),
            client_ip=client_ip,
            user_agent=user_agent
        )
    
    async def _handle_error(
        self,
        error: Exception,
        request_context: HTTPRequestContext,
        response_time: float
    ) -> Dict[str, Any]:
        """
        Handle error and create structured response.
        
        Args:
            error: Exception that occurred
            request_context: HTTP request context
            response_time: Response time in milliseconds
            
        Returns:
            Structured error response dictionary
        """
        # Log error if enabled
        if self.log_errors:
            logger.error(
                f"HTTP request failed: {request_context.method} {request_context.path} "
                f"({response_time:.1f}ms) - {type(error).__name__}: {str(error)}",
                exc_info=True,
                extra={
                    'request_id': request_context.request_id,
                    'connection_id': request_context.connection_id,
                    'client_ip': request_context.client_ip,
                    'method': request_context.method,
                    'path': request_context.path,
                    'response_time_ms': response_time
                }
            )
        
        # Handle different error types
        if isinstance(error, HTTPException):
            # FastAPI HTTPException
            error_response = {
                "error": {
                    "code": "HTTP_EXCEPTION",
                    "message": error.detail,
                    "correlation_id": request_context.request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                "http_status_code": error.status_code
            }
        elif isinstance(error, HTTPTransportError):
            # HTTP transport specific error
            error_response = create_http_error_response(
                error=error,
                request_id=request_context.request_id,
                include_details=self.include_error_details
            )
            error_response["http_status_code"] = error.http_status_code
        elif isinstance(error, RAGError):
            # General RAG error
            error_response = create_http_error_response(
                error=error,
                request_id=request_context.request_id,
                include_details=self.include_error_details
            )
            error_response["http_status_code"] = map_error_to_http_status(error)
        else:
            # Unexpected error
            error_response = {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "correlation_id": request_context.request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                "http_status_code": 500
            }
            
            if self.include_error_details:
                error_response["error"]["details"] = {
                    "error_type": type(error).__name__,
                    "original_error": str(error)
                }
        
        # Add request context to error details
        if self.include_error_details:
            if "details" not in error_response["error"]:
                error_response["error"]["details"] = {}
            
            error_response["error"]["details"].update({
                "request_method": request_context.method,
                "request_path": request_context.path,
                "client_ip": request_context.client_ip,
                "response_time_ms": response_time,
                "transport": "http"
            })
        
        # Log error with Logfire
        logfire.error(
            "HTTP request error",
            error_code=error_response["error"]["code"],
            error_message=error_response["error"]["message"],
            http_status_code=error_response["http_status_code"],
            request_id=request_context.request_id,
            connection_id=request_context.connection_id,
            method=request_context.method,
            path=request_context.path,
            client_ip=request_context.client_ip,
            response_time_ms=response_time,
            error_type=type(error).__name__,
            component="http_error_handler"
        )
        
        return error_response


class HTTPErrorHandler:
    """
    Standalone HTTP error handler for use outside middleware.
    
    This class provides error handling functionality that can be used
    directly in route handlers or other HTTP processing code.
    """
    
    def __init__(self, include_error_details: bool = True):
        """
        Initialize HTTP error handler.
        
        Args:
            include_error_details: Whether to include detailed error information
        """
        self.include_error_details = include_error_details
    
    async def handle_error(
        self,
        error: Exception,
        operation: str,
        request_context: Optional[HTTPRequestContext] = None,
        **kwargs
    ) -> JSONResponse:
        """
        Handle error and return JSON response.
        
        Args:
            error: Exception that occurred
            operation: Name of the operation that failed
            request_context: Optional HTTP request context
            **kwargs: Additional context information
            
        Returns:
            JSONResponse with structured error information
        """
        correlation_id = kwargs.get('correlation_id') or str(uuid.uuid4())
        
        # Create error response
        if isinstance(error, HTTPTransportError):
            error_response = create_http_error_response(
                error=error,
                request_id=correlation_id,
                include_details=self.include_error_details
            )
            status_code = error.http_status_code
        else:
            error_response = handle_http_transport_error(
                error=error,
                operation=operation,
                request_method=request_context.method if request_context else None,
                request_path=request_context.path if request_context else None,
                client_ip=request_context.client_ip if request_context else None,
                correlation_id=correlation_id
            )
            status_code = error_response["http_status_code"]
        
        # Log error
        logger.error(
            f"HTTP error in {operation}: {type(error).__name__}: {str(error)}",
            exc_info=True,
            extra={
                'operation': operation,
                'correlation_id': correlation_id,
                'error_type': type(error).__name__
            }
        )
        
        # Log with Logfire
        logfire.error(
            f"HTTP error in {operation}",
            error_type=type(error).__name__,
            error_message=str(error),
            operation=operation,
            correlation_id=correlation_id,
            component="http_error_handler"
        )
        
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )
    
    @asynccontextmanager
    async def error_context(
        self,
        operation: str,
        request_context: Optional[HTTPRequestContext] = None,
        **kwargs
    ):
        """
        Context manager for automatic error handling.
        
        Args:
            operation: Name of the operation
            request_context: Optional HTTP request context
            **kwargs: Additional context information
            
        Yields:
            None
            
        Raises:
            JSONResponse: On error, raises JSONResponse with error details
        """
        try:
            yield
        except Exception as error:
            response = await self.handle_error(
                error=error,
                operation=operation,
                request_context=request_context,
                **kwargs
            )
            # Convert JSONResponse to exception for FastAPI
            raise HTTPException(
                status_code=response.status_code,
                detail=response.body.decode() if hasattr(response.body, 'decode') else str(response.body)
            )


# Utility functions for common HTTP error scenarios

async def handle_connection_error(
    error: Exception,
    connection_id: str,
    client_ip: Optional[str] = None,
    operation: str = "connection"
) -> HTTPConnectionError:
    """
    Handle connection-related errors.
    
    Args:
        error: Original exception
        connection_id: Connection identifier
        client_ip: Client IP address
        operation: Operation that failed
        
    Returns:
        HTTPConnectionError instance
    """
    return HTTPConnectionError(
        message=f"Connection error during {operation}: {str(error)}",
        connection_id=connection_id,
        client_ip=client_ip,
        original_error=str(error),
        correlation_id=str(uuid.uuid4())
    )


async def handle_request_validation_error(
    error: Exception,
    request_context: HTTPRequestContext,
    field_name: Optional[str] = None
) -> HTTPRequestError:
    """
    Handle request validation errors.
    
    Args:
        error: Original validation exception
        request_context: HTTP request context
        field_name: Name of the field that failed validation
        
    Returns:
        HTTPRequestError instance
    """
    return HTTPRequestError(
        message=f"Request validation failed: {str(error)}",
        request_method=request_context.method,
        request_path=request_context.path,
        request_id=request_context.request_id,
        original_error=str(error),
        correlation_id=request_context.request_id
    )


async def handle_response_error(
    error: Exception,
    request_id: str,
    response_type: str = "json"
) -> HTTPResponseError:
    """
    Handle response generation errors.
    
    Args:
        error: Original exception
        request_id: Request identifier
        response_type: Type of response being generated
        
    Returns:
        HTTPResponseError instance
    """
    return HTTPResponseError(
        message=f"Response generation failed: {str(error)}",
        request_id=request_id,
        response_type=response_type,
        original_error=str(error),
        correlation_id=request_id
    )


# Error handler factory functions

def create_http_error_handler(
    include_details: bool = True,
    log_errors: bool = True
) -> HTTPErrorHandler:
    """
    Create HTTP error handler instance.
    
    Args:
        include_details: Whether to include error details in responses
        log_errors: Whether to log errors automatically
        
    Returns:
        HTTPErrorHandler instance
    """
    return HTTPErrorHandler(include_error_details=include_details)


def create_http_error_middleware(
    include_details: bool = True,
    log_errors: bool = True
) -> type:
    """
    Create HTTP error middleware class.
    
    Args:
        include_details: Whether to include error details in responses
        log_errors: Whether to log errors automatically
        
    Returns:
        HTTPErrorHandlerMiddleware class configured with parameters
    """
    class ConfiguredHTTPErrorMiddleware(HTTPErrorHandlerMiddleware):
        def __init__(self, app: ASGIApp):
            super().__init__(
                app=app,
                include_error_details=include_details,
                log_errors=log_errors
            )
    
    return ConfiguredHTTPErrorMiddleware