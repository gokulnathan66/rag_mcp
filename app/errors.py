from .models import ErrorResponse


class RAGError(Exception):
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def to_error_response(exc: RAGError) -> ErrorResponse:
    return ErrorResponse(
        error_code=exc.code,
        error_message=exc.message,
        error_details=exc.details,
    )
