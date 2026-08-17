"""Entrypoint FastAPI untuk service AI CrossInspect.

Satu container melayani beberapa modul. Setiap modul memiliki router sendiri di
``app/api/routes/`` dan didaftarkan di sini, supaya modul tidak saling import.

Terdaftar saat ini: ``health`` saja. Router ``document`` (Modul 1) menyusul
bersama kontrak JSON-nya; vision (Modul 2) dan crosscheck didaftarkan oleh
pemiliknya masing-masing dengan menambahkan satu baris ``include_router``.
"""

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    default_response_class=ORJSONResponse,
)

app.include_router(health.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "health": "/health"}
