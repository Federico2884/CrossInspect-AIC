"""Batas (*seam*) antara HTTP layer dan engine deteksi.

Pola yang sama dengan ``modules/document/engines/base.py``: mock hari ini, YOLO
saat torch tersedia, dan model hasil training ulang berikutnya — semuanya
mengimplementasikan protokol ini, sehingga bentuk response tidak pernah berubah.

Modul HTTP tidak boleh mengimpor engine konkret selain lewat ``get_engine()``
di ``service.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.modules.vision.schemas import InspectResponse


@dataclass(frozen=True)
class ImagePayload:
    """Foto yang sudah lolos validasi upload."""

    content: bytes
    media_type: str  # hasil sniff magic bytes, bukan header dari klien
    width: int
    height: int
    filename: str | None = None
    scenario: str | None = None


@runtime_checkable
class VisionEngine(Protocol):
    name: str

    def inspect(self, payload: ImagePayload) -> InspectResponse: ...
