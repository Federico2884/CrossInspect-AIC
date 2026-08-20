"""Test orkestrasi engine Qwen2-VL — tanpa torch dan tanpa bobot model.

Modul engine mengimpor torch di puncak berkas, jadi di image test yang ringan
ia tidak bisa diimpor sama sekali. Solusinya: pasang modul tiruan **hanya bila
yang asli memang tidak ada**. Di image ML, test yang sama memakai pustaka
sungguhan tanpa perubahan.

Yang diuji di sini bukan kemampuan model, melainkan hal-hal di sekelilingnya
yang selama ini hanya teruji lewat tangan: penomoran halaman, pemotongan
halaman, ketahanan saat satu halaman gagal, dan janji kontrak bahwa
``meta.debug`` tetap kosong selama debug tidak dinyalakan.
"""

import sys
import types

import pytest
from PIL import Image

from app.core.config import get_settings


def _stub(name: str, **attributes) -> None:
    """Pasang modul tiruan bila yang asli tidak terpasang."""
    if name in sys.modules:
        return
    try:
        __import__(name)
        return
    except ImportError:
        module = types.ModuleType(name)
        for key, value in attributes.items():
            setattr(module, key, value)
        sys.modules[name] = module


_stub("torch")
_stub("transformers", AutoProcessor=object, Qwen2VLForConditionalGeneration=object)
_stub("qwen_vl_utils", process_vision_info=lambda messages: ([], []))

from app.modules.document.engines import qwen  # noqa: E402
from app.modules.document.extraction import ExtractedPage  # noqa: E402
from app.modules.document.rendering import RenderResult  # noqa: E402
from app.modules.document.schemas import Item, UnitNormalized  # noqa: E402


def page_image() -> Image.Image:
    return Image.new("RGB", (80, 100), "white")


def rendered(pages: int = 1, total: int | None = None) -> RenderResult:
    total = pages if total is None else total
    images = [page_image() for _ in range(pages)]
    return RenderResult(
        pages=images,
        page_count=len(images),
        total_pages=total,
        truncated=total > len(images),
    )


def one_row(page: int) -> ExtractedPage:
    return ExtractedPage(
        ok=True,
        raw_text=f'{{"items": [{{"item_name": "Barang hal {page}"}}]}}',
        document_number="SJ-1" if page == 1 else None,
        items=[
            Item(
                item_name=f"Barang hal {page}",
                quantity=page,
                unit_raw="Dus",
                unit_normalized=UnitNormalized.BOX,
                source_page=page,
            )
        ],
        item_confidences=[0.9],
        document_number_confidence=0.9 if page == 1 else 0.0,
    )


@pytest.fixture
def engine(monkeypatch):
    """Engine dengan model dan pembacaan halaman dipalsukan."""
    monkeypatch.setattr(qwen, "_load", lambda model_id: (object(), object()))
    monkeypatch.setattr(
        qwen,
        "_read_page",
        lambda model, processor, image, page_number: one_row(page_number),
    )
    get_settings.cache_clear()
    yield qwen.QwenEngine()
    get_settings.cache_clear()


def payload():
    from app.modules.document.engines.base import DocumentPayload

    return DocumentPayload(content=b"%PDF-1.7", media_type="application/pdf")


def test_every_rendered_page_is_read_and_numbered(engine, monkeypatch):
    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(3))

    response = engine.parse(payload())

    assert response.page_count == 3
    assert [item.source_page for item in response.items] == [1, 2, 3]


def test_truncated_render_becomes_a_warning_with_the_real_total(engine, monkeypatch):
    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(10, total=14))

    response = engine.parse(payload())

    truncation = [w for w in response.warnings if w.code == "PAGE_LIMIT_TRUNCATED"]
    assert len(truncation) == 1
    assert "14" in truncation[0].message
    assert response.page_count == 10


def test_model_page_cap_below_the_render_cap_still_reports_honestly(engine, monkeypatch):
    """page_count harus berarti 'halaman yang benar-benar dibaca'."""
    monkeypatch.setenv("AI_QWEN_MAX_MODEL_PAGES", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(5))

    response = engine.parse(payload())

    assert response.page_count == 2
    assert len(response.items) == 2
    assert any(w.code == "PAGE_LIMIT_TRUNCATED" for w in response.warnings)


def test_one_failing_page_does_not_sink_the_document(engine, monkeypatch):
    def explode_on_page_two(model, processor, image, page_number):
        if page_number == 2:
            raise RuntimeError("halaman ini meledak")
        return one_row(page_number)

    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(3))
    monkeypatch.setattr(qwen, "_read_page", explode_on_page_two)

    response = engine.parse(payload())

    # Halaman 1 dan 3 tetap terbaca; halaman 2 hilang tanpa melempar.
    assert [item.source_page for item in response.items] == [1, 3]
    assert response.page_count == 3


def test_debug_stays_empty_unless_switched_on(engine, monkeypatch):
    """Kontrak menjanjikan bentuk response tidak berubah; debug default null."""
    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(2))

    assert engine.parse(payload()).meta.debug is None


def test_debug_carries_raw_pages_when_switched_on(monkeypatch):
    monkeypatch.setenv("AI_DEBUG", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(qwen, "_load", lambda model_id: (object(), object()))
    monkeypatch.setattr(
        qwen, "_read_page", lambda m, p, image, page_number: one_row(page_number)
    )
    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(2))

    debug = qwen.QwenEngine().parse(payload()).meta.debug
    get_settings.cache_clear()

    assert debug is not None
    assert len(debug["raw_pages"]) == 2
    assert "Barang hal 1" in debug["raw_pages"][0]


def test_meta_engine_is_the_model_id_not_a_label(engine, monkeypatch):
    """Kontrak: meta.engine-lah cara klien tahu engine mana yang menjawab."""
    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(1))

    response = engine.parse(payload())

    assert response.meta.engine == get_settings().qwen_model_id
    assert response.meta.scenario is None


def test_document_fields_come_from_the_first_page_that_has_them(engine, monkeypatch):
    monkeypatch.setattr(qwen, "render_pages", lambda *a, **k: rendered(3))

    response = engine.parse(payload())

    assert response.document_number == "SJ-1"


# --------------------------------------------------------------------------
# Pemilihan engine
# --------------------------------------------------------------------------


def test_get_engine_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("AI_ENGINE", raising=False)
    get_settings.cache_clear()

    from app.modules.document.service import get_engine

    assert get_engine().name == "mock"
    get_settings.cache_clear()


@pytest.mark.parametrize("value", ["qwen2vl", "qwen", "Qwen2-VL"])
def test_get_engine_selects_qwen_by_env(monkeypatch, value):
    monkeypatch.setenv("AI_ENGINE", value)
    get_settings.cache_clear()

    from app.modules.document.service import get_engine

    assert get_engine().name == get_settings().qwen_model_id
    get_settings.cache_clear()
