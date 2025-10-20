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
