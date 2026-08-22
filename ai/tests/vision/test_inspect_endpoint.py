"""Test HTTP Modul 2: validasi upload, envelope error, dan bentuk response."""

import pytest

from app.modules.vision.engines.mock import SCENARIOS

from .conftest import CORRUPT_PNG_BYTES, JPEG_BYTES, PNG_BYTES, TEXT_BYTES

ENDPOINT = "/vision/inspect"


def test_happy_path_returns_contract_shaped_json(client, png_upload):
    response = client.post(ENDPOINT, files=png_upload)
    assert response.status_code == 200

    body = response.json()
    assert body["meta"]["engine"] == "mock"
    assert body["meta"]["device"] == "cpu"
    assert body["meta"]["scenario"] in SCENARIOS
    assert set(body) == {
        "detected_count",
        "class_counts",
        "detections",
        "count_confidence",
        "defect",
        "warnings",
        "meta",
    }


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_explicit_scenario_is_honoured_and_echoed(client, scenario):
    response = client.post(
        ENDPOINT,
        files={"file": ("stack.png", PNG_BYTES, "image/png")},
        data={"scenario": scenario},
    )
    assert response.status_code == 200
    assert response.json()["meta"]["scenario"] == scenario


def test_jpeg_is_accepted(client):
    response = client.post(ENDPOINT, files={"file": ("stack.jpg", JPEG_BYTES, "image/jpeg")})
    assert response.status_code == 200


def test_real_dimensions_are_reported(client, png_upload):
    meta = client.post(ENDPOINT, files=png_upload).json()["meta"]
    assert (meta["image_width"], meta["image_height"]) == (1280, 960)


def test_text_file_renamed_as_png_is_rejected(client):
    # Sniffing pakai magic bytes, bukan nama berkas atau Content-Type.
    response = client.post(ENDPOINT, files={"file": ("stack.png", TEXT_BYTES, "image/png")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_pdf_is_rejected_by_vision(client):
    # Modul 1 menerima PDF, Modul 2 tidak — batas itu harus tegas.
    response = client.post(ENDPOINT, files={"file": ("doc.pdf", b"%PDF-1.7\n", "application/pdf")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_corrupt_image_with_valid_magic_bytes_is_rejected(client):
    response = client.post(ENDPOINT, files={"file": ("x.png", CORRUPT_PNG_BYTES, "image/png")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNREADABLE_IMAGE"


def test_empty_file_is_rejected(client):
    response = client.post(ENDPOINT, files={"file": ("empty.png", b"", "image/png")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_FILE"


def test_unknown_scenario_is_rejected(client):
    response = client.post(
        ENDPOINT,
        files={"file": ("stack.png", PNG_BYTES, "image/png")},
        data={"scenario": "tidak_ada"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_SCENARIO"


def test_missing_file_field_uses_the_shared_error_envelope(client):
    response = client.post(ENDPOINT)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert "detail" not in body  # bentuk bawaan FastAPI tidak boleh bocor


def test_engine_status_endpoint_reports_mock(client):
    body = client.get("/vision/engine").json()
    assert body["configured"] == "mock"
    assert body["active"] == "mock"


def test_startup_warmup_runs_and_does_not_block_the_service():
    # TestClient sebagai context manager menjalankan lifespan, jadi ini benar-
    # benar menguji jalur startup — bukan sekadar mengimpor app.
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as started:
        assert started.get("/health").json()["status"] == "ok"


def test_warmup_failure_does_not_kill_the_service(monkeypatch):
    # Modul 1 tidak boleh ikut mati kalau bobot Modul 2 bermasalah.
    from fastapi.testclient import TestClient

    import app.main as main

    def _boom() -> str:
        raise RuntimeError("bobot rusak")

    monkeypatch.setattr(main, "warmup_vision", _boom)
    with TestClient(main.app) as started:
        assert started.get("/health").status_code == 200
        parsed = started.post(
            "/document/parse",
            files={"file": ("s.pdf", b"%PDF-1.7\n" + b"\x00" * 8, "application/pdf")},
        )
        assert parsed.status_code == 200


def test_document_module_still_works(client):
    # Modul 1 tidak boleh rusak oleh penambahan Modul 2.
    response = client.post(
        "/document/parse",
        files={"file": ("sj.pdf", b"%PDF-1.7\n" + b"\x00" * 32, "application/pdf")},
    )
    assert response.status_code == 200
