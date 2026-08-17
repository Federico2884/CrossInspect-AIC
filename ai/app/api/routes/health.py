"""Liveness probe.

Dipakai oleh HEALTHCHECK di Dockerfile dan oleh ``depends_on: service_healthy``
di compose, jadi endpoint ini harus tetap murah: tidak menyentuh model,
tidak melakukan I/O.
"""

import platform

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "device": "cpu",  # CPU-only by design — tidak ada code path GPU
        "python": platform.python_version(),
    }
