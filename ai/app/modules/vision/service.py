"""Orkestrator Modul 2: validasi foto -> engine -> response.

Engine-agnostic. Menukar bobot atau berpindah dari mock ke YOLO hanya menyentuh
``get_engine()``.

Validasi upload ditulis terpisah dari milik Modul 1 karena himpunan tipe yang
diterima memang berbeda: Modul 1 menerima PDF, Modul 2 tidak — foto tumpukan
barang tidak pernah datang sebagai PDF, dan menerimanya hanya membuka jalur
kode yang tidak pernah dipakai.
"""

from __future__ import annotations

import time
from io import BytesIO

from app.core.config import get_settings
from app.core.errors import ServiceError
from app.modules.vision.engines import yolo
from app.modules.vision.engines.base import ImagePayload, VisionEngine
from app.modules.vision.engines.mock import SCENARIOS, MockEngine
from app.modules.vision.schemas import InspectResponse

# Magic bytes -> media type. Ekstensi dan Content-Type dari klien tidak
# dipercaya: keduanya gampang dipalsukan dan sering salah dari kamera ponsel.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def get_engine() -> VisionEngine:
    """Engine aktif, sesuai ``AI_VISION_ENGINE``.

    Mode 'auto' membuat service tetap menyala di image slim (yang tidak punya
    torch) alih-alih gagal saat startup — di sana vision dilayani mock.
    """
    setting = get_settings().vision_engine

    if setting == "mock":
        return MockEngine()

    if setting == "yolo":
        if not yolo.is_available():
            raise ServiceError(
                503,
                "VISION_ENGINE_UNAVAILABLE",
                "YOLO engine dipaksa aktif tetapi ultralytics atau bobot model tidak tersedia.",
                f"expected weights at {get_settings().vision_model_file}",
            )
        return yolo.YoloEngine()

    return yolo.YoloEngine() if yolo.is_available() else MockEngine()


def warmup() -> str:
    """Muat bobot saat startup, bukan saat request pertama.

    Diukur di CPU: memuat bobot ~4 detik, inferensinya sendiri ~120 ms. Tanpa
    pemanasan ini, seluruh biaya itu jatuh ke penglihat pertama — yang saat
    demo biasanya juri. Mengembalikan nama engine yang aktif.
    """
    engine = get_engine()
    if engine.name == "yolo":
        yolo.preload()
    return engine.name


def sniff_media_type(content: bytes) -> str | None:
    for signature, media_type in _SIGNATURES:
        if content.startswith(signature):
            return media_type
    # WebP tidak punya signature di offset 0: 'RIFF' lalu 'WEBP' di byte ke-8.
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def read_dimensions(content: bytes) -> tuple[int, int]:
    """Lebar & tinggi asli foto.

    Dibaca lebih dulu di sini supaya ``meta.image_width/height`` selalu terisi
    walau engine-nya mock — Laravel memakainya untuk menskalakan bbox.
    """
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ServiceError(
            422,
            "UNREADABLE_IMAGE",
            "Berkas terlihat seperti gambar tetapi isinya tidak bisa dibaca.",
            str(exc),
        ) from exc

    if width < 1 or height < 1:
        raise ServiceError(
            422, "UNREADABLE_IMAGE", "Dimensi gambar tidak valid.", f"{width}x{height}"
        )
    return width, height


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
            "Only PNG, JPEG, and WebP images are supported.",
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


def inspect_image(
    content: bytes,
    filename: str | None = None,
    scenario: str | None = None,
) -> InspectResponse:
    started = time.perf_counter()

    media_type = validate_upload(content, filename)
    width, height = read_dimensions(content)
    payload = ImagePayload(
        content=content,
        media_type=media_type,
        width=width,
        height=height,
        filename=filename,
        scenario=validate_scenario(scenario),
    )

    response = get_engine().inspect(payload)
    response.meta.processing_ms = int((time.perf_counter() - started) * 1000)
    return response
