"""Test rendering: hal-hal yang bisa merusak masukan engine visi di step 4.

PDF contoh dibangun di memori memakai PyMuPDF, bukan berkas biner yang
di-commit — mengikuti alasan yang sama seperti ``conftest.py``.
"""

import io

import fitz
import pytest
from PIL import Image

from app.core.errors import ServiceError
from app.modules.document.rendering import render_pages

# Ukuran A4 dalam titik (1/72 inci), dipakai PyMuPDF sebagai satuan halaman.
A4_POINTS = (595, 842)


def make_pdf(page_count: int = 1, size: tuple[int, int] = A4_POINTS) -> bytes:
    """PDF sungguhan berisi ``page_count`` halaman A4 bertulisan."""
    document = fitz.open()
    for index in range(page_count):
        page = document.new_page(width=size[0], height=size[1])
        page.insert_text((72, 72), f"Surat Jalan halaman {index + 1}", fontsize=14)
    content = document.tobytes()
    document.close()
    return content


def make_image(fmt: str, size: tuple[int, int] = (800, 600)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    return buffer.getvalue()


def test_renders_every_page_of_a_multi_page_pdf():
    result = render_pages(make_pdf(3), "application/pdf")

    assert result.page_count == 3
    assert result.total_pages == 3
    assert result.truncated is False
    assert len(result.pages) == 3
    assert all(page.mode == "RGB" for page in result.pages)


def test_page_limit_truncates_and_reports_the_real_total():
    """Batas 10 halaman ditegakkan, tetapi jumlah asli tetap dilaporkan.

    ``total_pages`` yang jujur itulah yang membuat pemanggil bisa memancarkan
    PAGE_LIMIT_TRUNCATED dengan angka yang benar.
    """
    result = render_pages(make_pdf(12), "application/pdf", max_pages=10)

    assert result.page_count == 10
    assert result.total_pages == 12
    assert result.truncated is True
    assert len(result.pages) == 10


def test_a4_at_300_dpi_lands_near_2480x3508():
    # max_long_edge=0 mematikan pengecilan, supaya yang diuji benar-benar DPI-nya.
    result = render_pages(make_pdf(1), "application/pdf", dpi=300, max_long_edge=0)

    width, height = result.pages[0].size
    assert width == pytest.approx(2480, abs=4)
    assert height == pytest.approx(3508, abs=4)


def test_long_edge_cap_scales_down_and_keeps_aspect_ratio():
    uncapped = render_pages(make_pdf(1), "application/pdf", dpi=300, max_long_edge=0)
    capped = render_pages(make_pdf(1), "application/pdf", dpi=300, max_long_edge=1600)

    assert max(capped.pages[0].size) == 1600

    before = uncapped.pages[0].width / uncapped.pages[0].height
    after = capped.pages[0].width / capped.pages[0].height
    assert after == pytest.approx(before, rel=0.01)


def test_small_pages_are_not_upscaled():
    """Batas hanya memperkecil. Memperbesar cuma menambah piksel palsu."""
    result = render_pages(make_pdf(1), "application/pdf", dpi=36, max_long_edge=1600)

    assert max(result.pages[0].size) < 1600


@pytest.mark.parametrize(
    ("fmt", "media_type"),
    [("PNG", "image/png"), ("JPEG", "image/jpeg")],
)
def test_images_become_exactly_one_page(fmt: str, media_type: str):
    result = render_pages(make_image(fmt), media_type)

    assert result.page_count == 1
    assert result.total_pages == 1
    assert result.truncated is False
    assert result.pages[0].mode == "RGB"


def test_corrupt_pdf_raises_service_error_not_a_crash():
    """Magic bytes benar, isinya sampah — harus jadi 422, bukan traceback."""
    with pytest.raises(ServiceError) as excinfo:
        render_pages(b"%PDF-1.7\nrusak sama sekali\n", "application/pdf")

    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "UNSUPPORTED_FILE_TYPE"


def test_unrenderable_media_type_is_rejected():
    with pytest.raises(ServiceError) as excinfo:
        render_pages(b"whatever", "text/plain")

    assert excinfo.value.status_code == 422


def test_defaults_come_from_settings():
    """Tanpa argumen eksplisit, nilai dari config yang dipakai (300 DPI, 1600 px)."""
    result = render_pages(make_pdf(1), "application/pdf")

    assert max(result.pages[0].size) == 1600
