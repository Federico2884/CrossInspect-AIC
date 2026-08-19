"""Fixture bersama untuk test Modul 1.

Berkas contoh dibangun dari magic bytes di memori, bukan file biner yang
di-commit: repo tetap ringan dan setiap test jelas menunjukkan byte apa yang
sedang diuji.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Cukup untuk lolos sniffing; isi setelah signature tidak dibaca engine mock.
PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
TEXT_BYTES = "Surat Jalan nomor SJ/2026/08/00142 — plain text, bukan PDF.".encode()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def pdf_upload() -> dict:
    return {"file": ("surat-jalan.pdf", PDF_BYTES, "application/pdf")}
