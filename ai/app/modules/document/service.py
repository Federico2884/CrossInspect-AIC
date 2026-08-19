"""Orkestrator Modul 1: validasi upload -> engine -> response.

Engine-agnostic. Saat step 4 masuk, hanya ``get_engine()`` yang berubah.
"""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.errors import ServiceError
from app.modules.document.engines.base import DocumentEngine, DocumentPayload
from app.modules.document.engines.mock import SCENARIOS, MockEngine
from app.modules.document.schemas import ParseResponse

# Magic bytes -> media type. Ekstensi dan Content-Type dari klien tidak
# dipercaya: keduanya gampang dipalsukan dan sering salah dari browser.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def get_engine() -> DocumentEngine:
    """Engine aktif. Step 4 menukar ini dengan Qwen2-VL di balik protokol yang sama."""
    return MockEngine()


def sniff_media_type(content: bytes) -> str | None:
    for signature, media_type in _SIGNATURES:
        if content.startswith(signature):
            return media_type
    return None


def validate_upload(content: bytes, filename: str | None) -> str:
    """Kembalikan media type hasil sniff, atau lempar ServiceError."""
    settings = get_settings()

    if not content:
        raise ServiceError(422, "EMPTY_FILE", "Uploaded file is empty.", filename)

    if len(content) > settings.max_upload_bytes:
        raise ServiceError(
            413,
            "FILE_TOO_LARGE",
            f"File exceeds the {settings.max_upload_mb} MB limit.",
            f"received {len(content)} bytes",
        )

    media_type = sniff_media_type(content)
    if media_type is None:
        raise ServiceError(
            422,
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, PNG, and JPEG files are supported.",
            filename,
        )
    return media_type


def validate_scenario(scenario: str | None) -> str | None:
    """Skenario mock bersifat opsional; bila diisi harus salah satu yang dikenal.

    Menolak nilai asing lebih baik daripada diam-diam jatuh ke hash — kalau
    Laravel salah ketik nama skenario, kesalahan itu harus terlihat.
    """
    if scenario is None or scenario == "":
        return None
    if scenario not in SCENARIOS:
        raise ServiceError(
            422,
            "UNKNOWN_SCENARIO",
            f"Unknown scenario '{scenario}'.",
            f"expected one of: {', '.join(SCENARIOS)}",
        )
    return scenario


def parse_document(
    content: bytes,
    filename: str | None = None,
    scenario: str | None = None,
) -> ParseResponse:
    started = time.perf_counter()

    media_type = validate_upload(content, filename)
    payload = DocumentPayload(
        content=content,
        media_type=media_type,
        filename=filename,
        scenario=validate_scenario(scenario),
    )

    response = get_engine().parse(payload)
    response.meta.processing_ms = int((time.perf_counter() - started) * 1000)
    return response
