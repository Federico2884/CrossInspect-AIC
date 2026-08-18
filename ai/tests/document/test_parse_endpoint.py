"""Test HTTP: validasi upload, envelope error, dan bentuk response."""

import pytest

from app.modules.document.engines.mock import SCENARIOS

from .conftest import JPEG_BYTES, PDF_BYTES, PNG_BYTES, TEXT_BYTES

ENDPOINT = "/document/parse"


def test_happy_path_returns_contract_shaped_json(client, pdf_upload):
    response = client.post(ENDPOINT, files=pdf_upload)
    assert response.status_code == 200

    body = response.json()
    assert body["meta"]["engine"] == "mock"
    assert body["meta"]["device"] == "cpu"
    assert body["meta"]["scenario"] in SCENARIOS
    assert set(body) == {
        "document_type",
        "document_number",
        "document_date",
        "sender",
        "recipient",
        "page_count",
        "items",
        "confidence",
        "warnings",
        "meta",
    }


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_explicit_scenario_is_honoured_and_echoed(client, scenario):
    response = client.post(
        ENDPOINT,
        files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
        data={"scenario": scenario},
    )
    assert response.status_code == 200
    assert response.json()["meta"]["scenario"] == scenario


@pytest.mark.parametrize(
    "content,filename",
    [(PDF_BYTES, "doc.pdf"), (PNG_BYTES, "doc.png"), (JPEG_BYTES, "doc.jpg")],
)
def test_accepts_pdf_png_and_jpeg(client, content, filename):
    upload = {"file": (filename, content, "application/octet-stream")}
    assert client.post(ENDPOINT, files=upload).status_code == 200


def test_processing_ms_is_populated(client, pdf_upload):
    assert client.post(ENDPOINT, files=pdf_upload).json()["meta"]["processing_ms"] >= 0


def test_unsupported_type_returns_422_envelope(client):
    response = client.post(ENDPOINT, files={"file": ("notes.txt", TEXT_BYTES, "text/plain")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_extension_and_content_type_are_not_trusted(client):
    # Berkas teks yang menyamar sebagai PDF harus tetap ditolak.
    response = client.post(ENDPOINT, files={"file": ("fake.pdf", TEXT_BYTES, "application/pdf")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_empty_file_returns_422(client):
    response = client.post(ENDPOINT, files={"file": ("empty.pdf", b"", "application/pdf")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_FILE"


def test_oversized_file_returns_413(client):
    oversized = PDF_BYTES + b"\x00" * (20 * 1024 * 1024)
    response = client.post(ENDPOINT, files={"file": ("big.pdf", oversized, "application/pdf")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_unknown_scenario_is_rejected_rather_than_ignored(client):
    response = client.post(
        ENDPOINT,
        files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
        data={"scenario": "definitely_not_a_scenario"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_SCENARIO"


def test_missing_file_field_returns_error_envelope(client):
    response = client.post(ENDPOINT, data={"scenario": "invoice"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_health_still_works(client):
    assert client.get("/health").status_code == 200
