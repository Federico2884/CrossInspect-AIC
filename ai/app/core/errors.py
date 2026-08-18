"""Envelope error seragam untuk seluruh service.

FastAPI secara default membalas ``{"detail": ...}``. Kontrak kita memakai
``{"error": {...}}`` supaya klien bisa membedakan kegagalan asli (413/422)
dari hasil parsing berkualitas rendah (200 + ``warnings[]``).
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ServiceError(Exception):
    """Kegagalan yang sudah diketahui penyebabnya dan aman dikirim ke klien."""

    def __init__(self, status_code: int, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail


def _envelope(status_code: int, code: str, message: str, detail: str | None) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "detail": detail}},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError) -> ORJSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> ORJSONResponse:
        return _envelope(exc.status_code, "HTTP_ERROR", str(exc.detail), None)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> ORJSONResponse:
        # Mis. field `file` tidak dikirim sama sekali.
        return _envelope(
            422, "INVALID_REQUEST", "Request body failed validation.", str(exc.errors())
        )
