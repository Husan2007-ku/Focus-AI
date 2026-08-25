"""
Loyihaga xos custom xatolar va ularni global tutuvchi (handler) funksiyalar.

Maqsad: foydalanuvchiga hech qachon xom Python traceback qaytmasin —
har doim bir xil formatdagi, tushunarli JSON javob qaytishi kerak.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class FocusAIException(Exception):
    """Barcha domain xatolari uchun asosiy klass."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "focusai_error"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        self.message = message
        if error_code:
            self.error_code = error_code
        super().__init__(message)


class NotFoundError(FocusAIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class UnauthorizedError(FocusAIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"


class ForbiddenError(FocusAIException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"


class ConflictError(FocusAIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class RateLimitError(FocusAIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"


class ExternalServiceError(FocusAIException):
    """Payme, Click, Claude API, Firebase kabi tashqi xizmatlar xatosi."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "external_service_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FocusAIException)
    async def focusai_exception_handler(
        request: Request, exc: FocusAIException
    ) -> JSONResponse:
        logger.warning(
            "handled_exception",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "internal_server_error",
                "message": "Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring.",
            },
        )
