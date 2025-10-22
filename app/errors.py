"""
Error handling and response formatting for RAG MCP Server.

This module provides:
- Structured error types for different failure scenarios
- Error response formatting with correlation IDs
- Error recovery strategies and retry logic
- Comprehensive error logging
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from .models import ErrorResponse


logger = logging.getLogger(__name__)


class RAGError(Exception):
    """
    Base exception class for RAG server errors.
    
    All custom exceptions inherit from this class to provide
    consistent error handling and response formatting.
    """
    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        correlation_id: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.retry_after = retry_after
        self.correlation_id = correlation_id or str(uuid.uuid4())
        super().__init__(message)


class FileAccessError(RAGError):
    """
    Exception raised when file access fails.
    
    Covers scenarios like:
    - File not found
    - Permission denied
    - File encoding issues
    """
    def __init__(
        self,
        message: str,
        file_path: str,
        original_error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        details = {
            'file_path': file_path,
            'error_type': 'file_access'
        }
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='FILE_ACCESS_ERROR',
            message=message,
            details=details,
            correlation_id=correlation_id
        )


class CSVParsingError(RAGError):
    """
    Exception raised when CSV parsing fails.
    
    Covers scenarios like:
    - Malformed CSV structure
    - Invalid row data
    - Encoding issues
    - Schema validation failures
    """
    def __init__(
        self,
        message: str,
        file_path: str,
        row_number: Optional[int] = None,
        original_error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        details = {
            'file_path': file_path,
            'error_type': 'csv_parsing'
        }
        if row_number is not None:
            details['row_number'] = row_number
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='CSV_PARSING_ERROR',
            message=message,
            details=details,
            correlation_id=correlation_id
        )


class EmbeddingError(RAGError):
    """
    Exception raised when embedding generation fails.
    
    Covers scenarios like:
    - FastEmbed model loading failures
    - Embedding generation errors
    - Invalid input text
    - Model compatibility issues
    """
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        original_error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_type': 'embedding_generation'
        }
        if model_name:
            details['model_name'] = model_name
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='EMBEDDING_ERROR',
            message=message,
            details=details,
            correlation_id=correlation_id
        )


class QdrantConnectionError(RAGError):
    """
    Exception raised when Qdrant database connection fails.
    
    Covers scenarios like:
    - Connection timeout
    - Authentication failure
    - Network errors
    - Service unavailable
    """
    def __init__(
        self,
        message: str,
        qdrant_url: Optional[str] = None,
        original_error: Optional[str] = None,
        retry_after: Optional[int] = 30,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_type': 'qdrant_connection'
        }
        if qdrant_url:
            details['qdrant_url'] = qdrant_url
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='QDRANT_CONNECTION_ERROR',
            message=message,
            details=details,
            retry_after=retry_after,
            correlation_id=correlation_id
        )


class QdrantOperationError(RAGError):
    """
    Exception raised when Qdrant operations fail.
    
    Covers scenarios like:
    - Collection not found
    - Upsert failures
    - Search errors
    - Invalid query parameters
    """
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        collection_name: Optional[str] = None,
        original_error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_type': 'qdrant_operation'
        }
        if operation:
            details['operation'] = operation
        if collection_name:
            details['collection_name'] = collection_name
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='QDRANT_OPERATION_ERROR',
            message=message,
            details=details,
            correlation_id=correlation_id
        )


class ValidationError(RAGError):
    """
    Exception raised when input validation fails.
    
    Covers scenarios like:
    - Invalid MCP request format
    - Missing required fields
    - Invalid parameter values
    - Schema validation failures
    """
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        invalid_value: Optional[Any] = None,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_type': 'validation'
        }
        if field_name:
            details['field_name'] = field_name
        if invalid_value is not None:
            details['invalid_value'] = str(invalid_value)
        
        super().__init__(
            code='VALIDATION_ERROR',
            message=message,
            details=details,
            correlation_id=correlation_id
        )


class WorkflowError(RAGError):
    """
    Exception raised when LangGraph workflow execution fails.
    
    Covers scenarios like:
    - Workflow state errors
    - Node execution failures
    - Workflow timeout
    - Checkpoint errors
    """
    def __init__(
        self,
        message: str,
        workflow_name: Optional[str] = None,
        node_name: Optional[str] = None,
        original_error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_type': 'workflow'
        }
        if workflow_name:
            details['workflow_name'] = workflow_name
        if node_name:
            details['node_name'] = node_name
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='WORKFLOW_ERROR',
            message=message,
            details=details,
            correlation_id=correlation_id
        )


# HTTP Transport Specific Errors

class HTTPTransportError(RAGError):
    """
    Base exception class for HTTP transport errors.
    
    All HTTP transport specific exceptions inherit from this class
    to provide consistent error handling and HTTP status code mapping.
    """
    def __init__(
        self,
        code: str,
        message: str,
        http_status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        correlation_id: Optional[str] = None
    ):
        self.http_status_code = http_status_code
        details = details or {}
        details['http_status_code'] = http_status_code
        details['error_type'] = 'http_transport'
        
        super().__init__(
            code=code,
            message=message,
            details=details,
            retry_after=retry_after,
            correlation_id=correlation_id
        )


class HTTPConnectionError(HTTPTransportError):
    """
    Exception raised when HTTP connection fails.
    
    Covers scenarios like:
    - Connection timeout
    - Connection refused
    - Network errors
    - Connection limit exceeded
    """
    def __init__(
        self,
        message: str,
        connection_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        original_error: Optional[str] = None,
        http_status_code: int = 503,
        retry_after: Optional[int] = 30,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_subtype': 'connection'
        }
        if connection_id:
            details['connection_id'] = connection_id
        if client_ip:
            details['client_ip'] = client_ip
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='HTTP_CONNECTION_ERROR',
            message=message,
            http_status_code=http_status_code,
            details=details,
            retry_after=retry_after,
            correlation_id=correlation_id
        )


class HTTPRequestError(HTTPTransportError):
    """
    Exception raised when HTTP request processing fails.
    
    Covers scenarios like:
    - Malformed requests
    - Invalid headers
    - Request timeout
    - Request size limits
    """
    def __init__(
        self,
        message: str,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        request_id: Optional[str] = None,
        original_error: Optional[str] = None,
        http_status_code: int = 400,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_subtype': 'request'
        }
        if request_method:
            details['request_method'] = request_method
        if request_path:
            details['request_path'] = request_path
        if request_id:
            details['request_id'] = request_id
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='HTTP_REQUEST_ERROR',
            message=message,
            http_status_code=http_status_code,
            details=details,
            correlation_id=correlation_id
        )


class HTTPResponseError(HTTPTransportError):
    """
    Exception raised when HTTP response generation fails.
    
    Covers scenarios like:
    - Response serialization errors
    - Response timeout
    - Response size limits
    - Streaming errors
    """
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        response_type: Optional[str] = None,
        original_error: Optional[str] = None,
        http_status_code: int = 500,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_subtype': 'response'
        }
        if request_id:
            details['request_id'] = request_id
        if response_type:
            details['response_type'] = response_type
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='HTTP_RESPONSE_ERROR',
            message=message,
            http_status_code=http_status_code,
            details=details,
            correlation_id=correlation_id
        )


class HTTPAuthenticationError(HTTPTransportError):
    """
    Exception raised when HTTP authentication fails.
    
    Covers scenarios like:
    - Missing authentication
    - Invalid credentials
    - Expired tokens
    - Authorization failures
    """
    def __init__(
        self,
        message: str,
        auth_type: Optional[str] = None,
        client_ip: Optional[str] = None,
        original_error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_subtype': 'authentication'
        }
        if auth_type:
            details['auth_type'] = auth_type
        if client_ip:
            details['client_ip'] = client_ip
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='HTTP_AUTHENTICATION_ERROR',
            message=message,
            http_status_code=401,
            details=details,
            correlation_id=correlation_id
        )


class HTTPRateLimitError(HTTPTransportError):
    """
    Exception raised when HTTP rate limits are exceeded.
    
    Covers scenarios like:
    - Request rate limiting
    - Connection rate limiting
    - Bandwidth limiting
    - Resource exhaustion
    """
    def __init__(
        self,
        message: str,
        limit_type: str,
        current_rate: Optional[float] = None,
        limit_threshold: Optional[float] = None,
        client_ip: Optional[str] = None,
        retry_after: Optional[int] = 60,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_subtype': 'rate_limit',
            'limit_type': limit_type
        }
        if current_rate is not None:
            details['current_rate'] = current_rate
        if limit_threshold is not None:
            details['limit_threshold'] = limit_threshold
        if client_ip:
            details['client_ip'] = client_ip
        
        super().__init__(
            code='HTTP_RATE_LIMIT_ERROR',
            message=message,
            http_status_code=429,
            details=details,
            retry_after=retry_after,
            correlation_id=correlation_id
        )


class HTTPServerError(HTTPTransportError):
    """
    Exception raised when HTTP server encounters internal errors.
    
    Covers scenarios like:
    - Server startup failures
    - Configuration errors
    - Resource exhaustion
    - Internal server errors
    """
    def __init__(
        self,
        message: str,
        server_component: Optional[str] = None,
        original_error: Optional[str] = None,
        http_status_code: int = 500,
        correlation_id: Optional[str] = None
    ):
        details = {
            'error_subtype': 'server'
        }
        if server_component:
            details['server_component'] = server_component
        if original_error:
            details['original_error'] = original_error
        
        super().__init__(
            code='HTTP_SERVER_ERROR',
            message=message,
            http_status_code=http_status_code,
            details=details,
            correlation_id=correlation_id
        )


def to_error_response(exc: RAGError) -> ErrorResponse:
    """
    Convert a RAGError to an ErrorResponse model.
    
    This function creates a structured error response that can be
    returned to MCP clients with all relevant error information.
    
    Args:
        exc: RAGError exception instance
        
    Returns:
        ErrorResponse model with error details
    """
    return ErrorResponse(
        error_code=exc.code,
        error_message=exc.message,
        error_details=exc.details,
        retry_after=exc.retry_after,
        correlation_id=exc.correlation_id
    )


def handle_exception(
    exc: Exception,
    operation: str,
    correlation_id: Optional[str] = None
) -> ErrorResponse:
    """
    Handle any exception and convert it to a structured ErrorResponse.
    
    This function provides a fallback for handling unexpected exceptions
    that don't inherit from RAGError.
    
    Args:
        exc: Exception instance
        operation: Name of the operation that failed
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        ErrorResponse model with error details
    """
    if isinstance(exc, RAGError):
        return to_error_response(exc)
    
    # Handle unexpected exceptions
    correlation_id = correlation_id or str(uuid.uuid4())
    
    logger.error(
        f"Unexpected error in {operation}: {str(exc)}",
        exc_info=True,
        extra={'correlation_id': correlation_id}
    )
    
    return ErrorResponse(
        error_code='INTERNAL_ERROR',
        error_message=f"An unexpected error occurred during {operation}",
        error_details={
            'operation': operation,
            'error_type': type(exc).__name__,
            'original_error': str(exc)
        },
        correlation_id=correlation_id
    )


def log_error(
    error: RAGError,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an error with structured context information.
    
    Args:
        error: RAGError instance to log
        context: Optional additional context information
    """
    log_context = {
        'error_code': error.code,
        'correlation_id': error.correlation_id,
        **error.details
    }
    
    if context:
        log_context.update(context)
    
    logger.error(
        f"[{error.correlation_id}] {error.code}: {error.message}",
        extra=log_context
    )


# HTTP Transport Error Handling Functions

def map_error_to_http_status(error: Exception) -> int:
    """
    Map an error to appropriate HTTP status code.
    
    Args:
        error: Exception instance
        
    Returns:
        HTTP status code
    """
    if isinstance(error, HTTPTransportError):
        return error.http_status_code
    elif isinstance(error, ValidationError):
        return 400  # Bad Request
    elif isinstance(error, FileAccessError):
        return 404  # Not Found
    elif isinstance(error, QdrantConnectionError):
        return 503  # Service Unavailable
    elif isinstance(error, EmbeddingError):
        return 502  # Bad Gateway
    elif isinstance(error, RAGError):
        return 500  # Internal Server Error
    else:
        return 500  # Internal Server Error


def create_http_error_response(
    error: Exception,
    request_id: Optional[str] = None,
    include_details: bool = True
) -> Dict[str, Any]:
    """
    Create structured HTTP error response from exception.
    
    Args:
        error: Exception instance
        request_id: Optional request ID for tracking
        include_details: Whether to include detailed error information
        
    Returns:
        HTTP error response dictionary
    """
    correlation_id = request_id or str(uuid.uuid4())
    
    if isinstance(error, RAGError):
        error_response = {
            "error": {
                "code": error.code,
                "message": error.message,
                "correlation_id": error.correlation_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        if include_details and error.details:
            error_response["error"]["details"] = error.details
        
        if error.retry_after:
            error_response["error"]["retry_after"] = error.retry_after
        
        # Add HTTP-specific information for HTTP transport errors
        if isinstance(error, HTTPTransportError):
            error_response["error"]["http_status_code"] = error.http_status_code
            error_response["error"]["transport"] = "http"
    else:
        # Handle non-RAG errors
        error_response = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        if include_details:
            error_response["error"]["details"] = {
                "error_type": type(error).__name__,
                "original_error": str(error)
            }
    
    return error_response


def handle_http_transport_error(
    error: Exception,
    operation: str,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    client_ip: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle HTTP transport errors with proper logging and response formatting.
    
    Args:
        error: Exception instance
        operation: Name of the operation that failed
        request_method: HTTP request method
        request_path: HTTP request path
        client_ip: Client IP address
        correlation_id: Optional correlation ID for tracking
        
    Returns:
        Structured error response dictionary with HTTP status code
    """
    correlation_id = correlation_id or str(uuid.uuid4())
    
    # Log the error with HTTP context
    http_context = {
        'operation': operation,
        'transport': 'http'
    }
    if request_method:
        http_context['request_method'] = request_method
    if request_path:
        http_context['request_path'] = request_path
    if client_ip:
        http_context['client_ip'] = client_ip
    
    if isinstance(error, RAGError):
        log_error(error, context=http_context)
    else:
        logger.error(
            f"[{correlation_id}] HTTP transport error in {operation}: {str(error)}",
            exc_info=True,
            extra=http_context
        )
    
    # Create structured error response
    error_response = create_http_error_response(error, correlation_id)
    
    # Add HTTP status code to response
    http_status_code = map_error_to_http_status(error)
    error_response["http_status_code"] = http_status_code
    
    # Add HTTP context to error details
    if "details" not in error_response["error"]:
        error_response["error"]["details"] = {}
    
    error_response["error"]["details"].update(http_context)
    
    return error_response


def create_http_validation_error(
    message: str,
    field_name: Optional[str] = None,
    invalid_value: Optional[Any] = None,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> HTTPRequestError:
    """
    Create HTTP validation error for malformed requests.
    
    Args:
        message: Error message
        field_name: Name of invalid field
        invalid_value: Invalid value provided
        request_method: HTTP request method
        request_path: HTTP request path
        correlation_id: Optional correlation ID
        
    Returns:
        HTTPRequestError instance
    """
    details = {}
    if field_name:
        details['field_name'] = field_name
    if invalid_value is not None:
        details['invalid_value'] = str(invalid_value)
    
    return HTTPRequestError(
        message=message,
        request_method=request_method,
        request_path=request_path,
        original_error=f"Validation failed for field '{field_name}': {invalid_value}",
        http_status_code=400,
        correlation_id=correlation_id
    )


def create_http_timeout_error(
    operation: str,
    timeout_seconds: int,
    connection_id: Optional[str] = None,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> HTTPConnectionError:
    """
    Create HTTP timeout error for connection or request timeouts.
    
    Args:
        operation: Operation that timed out
        timeout_seconds: Timeout duration in seconds
        connection_id: Optional connection ID
        request_id: Optional request ID
        correlation_id: Optional correlation ID
        
    Returns:
        HTTPConnectionError instance
    """
    message = f"{operation} timed out after {timeout_seconds} seconds"
    
    details = {
        'timeout_seconds': timeout_seconds,
        'operation': operation
    }
    if request_id:
        details['request_id'] = request_id
    
    return HTTPConnectionError(
        message=message,
        connection_id=connection_id,
        original_error=f"Timeout in {operation}",
        http_status_code=408,  # Request Timeout
        retry_after=min(timeout_seconds, 60),  # Suggest retry after timeout or 1 minute max
        correlation_id=correlation_id
    )


def create_http_server_error(
    message: str,
    component: str,
    original_error: Optional[Exception] = None,
    correlation_id: Optional[str] = None
) -> HTTPServerError:
    """
    Create HTTP server error for internal server issues.
    
    Args:
        message: Error message
        component: Server component that failed
        original_error: Original exception that caused the error
        correlation_id: Optional correlation ID
        
    Returns:
        HTTPServerError instance
    """
    return HTTPServerError(
        message=message,
        server_component=component,
        original_error=str(original_error) if original_error else None,
        http_status_code=500,
        correlation_id=correlation_id
    )
