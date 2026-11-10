"""
Centralised exception handling and custom exception classes.
"""
import uuid
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)


# ── Custom exceptions ─────────────────────────────────────────────────────────

class SchemeSaathiError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(SchemeSaathiError):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(message, code="NOT_FOUND", status_code=404)


class UnauthorizedError(SchemeSaathiError):
    def __init__(self, message: str = "Authentication required."):
        super().__init__(message, code="UNAUTHORIZED", status_code=401)


class ForbiddenError(SchemeSaathiError):
    def __init__(self, message: str = "You do not have permission to access this resource."):
        super().__init__(message, code="FORBIDDEN", status_code=403)


class ValidationError(SchemeSaathiError):
    def __init__(self, message: str = "Validation failed.", details: list | None = None):
        self.details = details or []
        super().__init__(message, code="VALIDATION_ERROR", status_code=422)


class ConflictError(SchemeSaathiError):
    def __init__(self, message: str = "Resource already exists."):
        super().__init__(message, code="CONFLICT", status_code=409)


class EligibilityEngineError(SchemeSaathiError):
    def __init__(self, message: str = "Eligibility evaluation failed."):
        super().__init__(message, code="ELIGIBILITY_ERROR", status_code=500)


# ── Error response builder ────────────────────────────────────────────────────

def _error_response(
    request_id: str,
    code: str,
    message: str,
    details: list | None = None,
    status_code: int = 500,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            },
            "request_id": request_id,
        },
    )


# ── Handler registration ──────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(SchemeSaathiError)
    async def scheme_saathi_error_handler(request: Request, exc: SchemeSaathiError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.warning("Application error [%s]: %s — %s", exc.code, exc.message, request.url)
        details = getattr(exc, "details", [])
        return _error_response(request_id, exc.code, exc.message, details, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        details = [
            {"field": " → ".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return _error_response(
            request_id,
            "VALIDATION_ERROR",
            "Request validation failed.",
            details,
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.error("Unhandled exception [%s]: %s", request.url, exc, exc_info=True)
        # Never expose internal stack traces to clients
        return _error_response(
            request_id,
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again later.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
