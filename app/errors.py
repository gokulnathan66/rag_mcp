from typing import Optional
from .models import ErrorResponse


class RAGError(Exception):
    """Base exception class for RAG server errors."""
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class FileAccessError(RAGError):
    """Exception raised when file access fails."""
    def __init__(
        self,
        message: str,
        file_path: str,
        original_error: Optional[str] = None
    ):
        details = {
            'file_path': file_path,
        }
        if original_error:
            details['original_error'] = original_error
        super().__init__(
            code='FILE_ACCESS_ERROR',
            message=message,
            details=details
        )


class CSVParsingError(RAGError):
    """Exception raised when CSV parsing fails."""
    def __init__(
        self,
        message: str,
        file_path: str,
        row_number: Optional[int] = None,
        original_error: Optional[str] = None
    ):
        details = {
            'file_path': file_path,
        }
        if row_number is not None:
            details['row_number'] = row_number
        if original_error:
            details['original_error'] = original_error
        super().__init__(
            code='CSV_PARSING_ERROR',
            message=message,
            details=details
        )


def to_error_response(exc: RAGError) -> ErrorResponse:
    """Convert a RAGError to an ErrorResponse model."""
    return ErrorResponse(
        error_code=exc.code,
        error_message=exc.message,
        error_details=exc.details,
    )
