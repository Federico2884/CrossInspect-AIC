"""Batas (*seam*) antara HTTP layer dan engine parsing.

Semua engine — mock hari ini, Qwen2-VL di step 4 — mengimplementasikan
protokol yang sama, sehingga penggantian engine tidak mengubah bentuk
response. Modul HTTP tidak boleh mengimpor engine konkret selain lewat
``get_engine()`` di ``service.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.modules.document.schemas import ParseResponse


@dataclass(frozen=True)
class DocumentPayload:
    """Berkas yang sudah lolos validasi upload."""

    content: bytes
    media_type: str  # hasil sniff magic bytes, bukan header dari klien
    filename: str | None = None
    scenario: str | None = None


@runtime_checkable
class DocumentEngine(Protocol):
    name: str

    def parse(self, payload: DocumentPayload) -> ParseResponse: ...
