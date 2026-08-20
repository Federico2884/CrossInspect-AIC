"""Lapisan HTTP Modul 3, plus satu jalur utuh dari kedua modul hulu."""

from io import BytesIO

import pytest
from PIL import Image

from app.core.config import get_settings
from tests.crosscheck.conftest import item, make_document, make_vision

PDF_BYTES = b"%PDF-1.4\n% Surat Jalan sintetis untuk test.\n"


def photo_bytes(width: int = 1280, height: int = 960) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(180, 140, 100)).save(buffer, format="PNG")
    return buffer.getvalue()


def body(document, vision) -> dict:
    # mode="json" supaya date dan enum jadi bentuk yang benar-benar dikirim klien.
    return {
        "document": document.model_dump(mode="json"),
        "vision": vision.model_dump(mode="json"),
    }


def test_returns_a_verdict(client):
    response = client.post(
        "/crosscheck", json=body(make_document([item(quantity=10)]), make_vision(detected_count=10))
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "MATCH"
    assert payload["quantity"]["difference"] == 0
    assert payload["identity"]["status"] == "unavailable"
    assert payload["meta"]["device"] == "cpu"


def test_is_fast_because_it_touches_no_model(client):
    response = client.post(
        "/crosscheck", json=body(make_document(), make_vision(detected_count=10))
    )
    # Modul 1 butuh ~200 detik; modul ini tidak boleh mendekati orde itu.
    assert response.json()["meta"]["processing_ms"] < 100


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"document": {"bukan": "kontrak"}, "vision": {}},
        {"document": None, "vision": None},
    ],
)
def test_malformed_body_uses_the_shared_error_envelope(client, payload):
    response = client.post("/crosscheck", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    # Bentuk bawaan FastAPI tidak boleh bocor.
    assert "detail" not in response.json()


def test_rejects_unknown_top_level_fields(client):
    payload = body(make_document(), make_vision())
    payload["catatan"] = "field yang tidak ada di kontrak"
    assert client.post("/crosscheck", json=payload).status_code == 422


def test_end_to_end_through_both_upstream_modules(client, monkeypatch):
    """Jalur sungguhan: dua endpoint hulu (engine mock) lalu vonis.

    Nilai test ini bukan pada angkanya — mock memilih fixture dari hash isi
    berkas, jadi cocok atau tidaknya kebetulan. Yang dibuktikan: respons kedua
    modul bisa langsung diteruskan ke ``/crosscheck`` tanpa disunting klien.
    """
    monkeypatch.setenv("AI_ENGINE", "mock")
    monkeypatch.setenv("AI_VISION_ENGINE", "mock")
    get_settings.cache_clear()

    try:
        parsed = client.post(
            "/document/parse", files={"file": ("sj.pdf", PDF_BYTES, "application/pdf")}
        )
        inspected = client.post(
            "/vision/inspect", files={"file": ("stack.png", photo_bytes(), "image/png")}
        )
        assert parsed.status_code == 200
        assert inspected.status_code == 200

        verdict = client.post(
            "/crosscheck", json={"document": parsed.json(), "vision": inspected.json()}
        )
    finally:
        get_settings.cache_clear()

    assert verdict.status_code == 200
    payload = verdict.json()
    assert payload["status"] in {"MATCH", "PARTIAL", "MISMATCH", "UNVERIFIABLE"}
    assert payload["meta"]["document_engine"] == "mock"
    assert payload["meta"]["vision_engine"] == "mock"
    # Selisih selalu konsisten dengan kedua angkanya, apa pun fixture yang terpilih.
    quantity = payload["quantity"]
    assert quantity["difference"] == quantity["detected_total"] - quantity["document_total"]
