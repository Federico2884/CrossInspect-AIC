"""Fixture bersama untuk test Modul 2.

Berbeda dengan Modul 1, di sini gambarnya harus **benar-benar bisa didekode**:
``service.read_dimensions`` membuka berkas dengan Pillow untuk mengisi
``meta.image_width/height``. Jadi magic bytes saja tidak cukup — gambar dibuat
di memori dengan Pillow, tetap tanpa berkas biner yang di-commit.
"""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.main import app


def make_image(width: int = 1280, height: int = 960, fmt: str = "PNG") -> bytes:
    image = Image.new("RGB", (width, height), color=(180, 140, 100))
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


PNG_BYTES = make_image()
JPEG_BYTES = make_image(fmt="JPEG")
SMALL_PNG_BYTES = make_image(width=320, height=240)
TEXT_BYTES = "Foto tumpukan kardus — plain text, bukan gambar.".encode()
# Magic bytes PNG yang benar tetapi isinya sampah: lolos sniff, gagal didekode.
CORRUPT_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def force_mock_engine(monkeypatch):
    """Semua test HTTP dijalankan di atas engine mock.

    Tanpa ini, hasil test bergantung pada apakah torch kebetulan terpasang di
    mesin yang menjalankannya — persis jenis ketidakpastian yang bikin CI
    hijau di laptop dan merah di container.
    """
    monkeypatch.setenv("AI_VISION_ENGINE", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def png_upload() -> dict:
    return {"file": ("tumpukan.png", PNG_BYTES, "image/png")}
