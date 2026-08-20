"""Rasterisasi dokumen menjadi gambar halaman untuk engine visi.

Engine mock tidak butuh piksel sama sekali; Qwen2-VL di step 4 butuh. Karena
itu modul ini **tidak** dipanggil dari ``service.py``: rendering bersifat malas
(*lazy*), dipanggil hanya oleh engine yang benar-benar memerlukan gambar. Jalur
request untuk mock tetap semurah sekarang, dan berkas contoh di test tidak perlu
berupa PDF sungguhan.

Dua jenis masukan diperlakukan seragam supaya engine tidak perlu tahu bedanya:

* PDF   -> dirasterisasi per halaman lewat PyMuPDF pada ``render_dpi`` (300).
* PNG/JPEG -> dibaca apa adanya sebagai satu halaman (DPI tidak relevan).

Keduanya keluar sebagai ``PIL.Image`` mode RGB.

Batas halaman ditegakkan di sini, tetapi *warning*-nya tidak. Yang memanggil
modul ini bertanggung jawab menerjemahkan ``RenderResult.truncated`` menjadi
warning ``PAGE_LIMIT_TRUNCATED`` dan mengisi ``page_count`` pada response —
lihat ``warnings.py``. Pemisahan ini disengaja: modul rendering tidak ikut
menyusun bentuk response.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import fitz  # PyMuPDF
from PIL import Image

from app.core.config import get_settings
from app.core.errors import ServiceError

PDF_MEDIA_TYPE = "application/pdf"
IMAGE_MEDIA_TYPES = frozenset({"image/png", "image/jpeg"})


@dataclass(frozen=True)
class RenderResult:
    """Halaman hasil render beserta jejak pemotongannya."""

    pages: list[Image.Image]
    page_count: int  # halaman yang benar-benar dirender (sesudah dibatasi)
    total_pages: int  # halaman yang dimiliki dokumen aslinya
    truncated: bool  # total_pages melebihi batas


def _downscale(image: Image.Image, max_long_edge: int | None) -> Image.Image:
    """Perkecil bila sisi terpanjang melewati batas, dengan rasio dipertahankan."""
    if not max_long_edge:
        return image

    long_edge = max(image.size)
    if long_edge <= max_long_edge:
        return image

    scale = max_long_edge / long_edge
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    return image.resize((width, height), Image.LANCZOS)


def _render_pdf(content: bytes, dpi: int, max_pages: int) -> tuple[list[Image.Image], int]:
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:  # PyMuPDF melempar beragam tipe untuk berkas rusak
        raise ServiceError(
            422,
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, PNG, and JPEG files are supported.",
            f"PDF could not be opened: {exc}",
        ) from exc

    with document:
        total_pages = document.page_count
        if total_pages == 0:
            raise ServiceError(
                422,
                "UNSUPPORTED_FILE_TYPE",
                "Only PDF, PNG, and JPEG files are supported.",
                "PDF contains no pages",
            )

        pages: list[Image.Image] = []
        for index in range(min(total_pages, max_pages)):
            pixmap = document.load_page(index).get_pixmap(dpi=dpi)
            # Lewat PPM, bukan pixmap.samples: PyMuPDF sudah menangani ruang
            # warna dan kanal alpha, jadi tidak perlu menebak jumlah kanal.
            pages.append(Image.open(io.BytesIO(pixmap.tobytes("ppm"))).convert("RGB"))

    return pages, total_pages


def _render_image(content: bytes) -> tuple[list[Image.Image], int]:
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except Exception as exc:
        raise ServiceError(
            422,
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, PNG, and JPEG files are supported.",
            f"image could not be decoded: {exc}",
        ) from exc

    return [image.convert("RGB")], 1


def render_pages(
    content: bytes,
    media_type: str,
    dpi: int | None = None,
    max_pages: int | None = None,
    max_long_edge: int | None = None,
) -> RenderResult:
    """Ubah berkas terunggah menjadi gambar halaman RGB.

    ``media_type`` harus berasal dari ``service.sniff_media_type`` — modul ini
    sengaja tidak melakukan sniffing sendiri supaya hanya ada satu sumber
    kebenaran soal deteksi format.

    Untuk ketiga argumen opsional, ``None`` berarti "pakai nilai dari config".
    Khusus ``max_long_edge``, isi ``0`` untuk mematikan pengecilan dan
    mendapatkan halaman pada resolusi DPI penuh.
    """
    settings = get_settings()
    dpi = dpi if dpi is not None else settings.render_dpi
    max_pages = max_pages if max_pages is not None else settings.max_pages
    if max_long_edge is None:
        max_long_edge = settings.render_max_long_edge

    if max_pages < 1:
        raise ValueError(f"max_pages must be >= 1, got {max_pages}")

    if media_type == PDF_MEDIA_TYPE:
        pages, total_pages = _render_pdf(content, dpi, max_pages)
    elif media_type in IMAGE_MEDIA_TYPES:
        pages, total_pages = _render_image(content)
    else:
        raise ServiceError(
            422,
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF, PNG, and JPEG files are supported.",
            f"cannot render media type {media_type!r}",
        )

    pages = [_downscale(page, max_long_edge) for page in pages]

    return RenderResult(
        pages=pages,
        page_count=len(pages),
        total_pages=total_pages,
        truncated=total_pages > len(pages),
    )
