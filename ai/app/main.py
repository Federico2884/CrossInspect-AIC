"""Entrypoint FastAPI untuk service AI CrossInspect.

Satu container melayani beberapa modul. Setiap modul memiliki router sendiri di
``app/api/routes/`` dan didaftarkan di sini, supaya modul tidak saling import.

Terdaftar saat ini: ``health`` dan ``document`` (Modul 1 — Document Parsing).
Vision (Modul 2) dan crosscheck didaftarkan oleh pemiliknya masing-masing
dengan menambahkan satu baris ``include_router``.
"""

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.api.routes import document, health
from app.core.config import get_settings
from app.core.errors import register_error_handlers

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    default_response_class=ORJSONResponse,
)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(document.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "health": "/health"}
