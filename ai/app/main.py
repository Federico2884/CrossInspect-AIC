"""Entrypoint FastAPI untuk service AI CrossInspect.

Satu container melayani beberapa modul. Setiap modul memiliki router sendiri di
``app/api/routes/`` dan didaftarkan di sini, supaya modul tidak saling import.

Terdaftar saat ini: ``health``, ``document`` (Modul 1 — Document Parsing),
``vision`` (Modul 2 — Physical Inspection), dan ``crosscheck`` (Modul 3 —
Cross-Check Engine).

Modul 1 dan 2 tidak saling import. Modul 3 adalah pengecualian yang disengaja:
ia konsumen keduanya, dan mengimpor schema mereka justru mencegah lahirnya
sumber kebenaran kedua — alasannya ada di ``modules/crosscheck/schemas.py``.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.api.routes import crosscheck, document, health, vision
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.modules.vision.service import warmup as warmup_vision

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Pemanasan model sebelum container dinyatakan sehat.

    Sengaja tidak fatal: kalau bobot bermasalah, service tetap menyala dan
    melayani lewat mock. Gagal total di sini akan membuat Modul 1 ikut mati
    hanya karena Modul 2 bermasalah.
    """
    try:
        logger.info("Vision engine aktif: %s", warmup_vision())
    except Exception:  # noqa: BLE001 - startup tidak boleh menjatuhkan service
        logger.exception("Pemanasan vision engine gagal; melanjutkan tanpa pemanasan.")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(document.router)
app.include_router(vision.router)
app.include_router(crosscheck.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "health": "/health"}
