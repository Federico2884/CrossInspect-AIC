"""Test ekstraksi: mengubah keluaran model yang tidak rapi menjadi kontrak.

Fokusnya pada kelakuan model di dunia nyata — pagar markdown, kalimat penutup,
field yang hilang, angka bergaya Indonesia — dan pada satu janji keras:
seburuk apa pun keluarannya, fungsi di sini tidak melempar.
"""

import json
from datetime import date

import pytest

from app.modules.document.extraction import (
    ExtractedPage,
    TokenSpan,
    assemble_response,
    build_item,
    build_token_spans,
    coerce_int,
    confidence_for_value,
    extract_json_object,
    extract_page,
    parse_indonesian_date,
    span_confidence,
    span_confidence_min,
)
from app.modules.document.schemas import DocumentType, UnitNormalized

PAYLOAD = {
    "document_type": "SURAT_JALAN",
    "document_number": "SJ/2026/08/00142",
    "document_date": "12 Agustus 2026",
    "sender": "PT Sinar Terang",
    "recipient": "Toko Maju",
    "items": [
        {
            "item_name": "Susu UHT 250ml",
            "sku": "ULT-250",
            "quantity": 10,
            "unit_raw": "Karton",
            "quantity_per_unit": 12,
        }
    ],
}


# --------------------------------------------------------------------------
# JSON yang tidak taat format
# --------------------------------------------------------------------------


def test_reads_plain_json():
    assert extract_json_object(json.dumps(PAYLOAD))["document_number"] == "SJ/2026/08/00142"


def test_reads_json_wrapped_in_markdown_fences():
    text = f"```json\n{json.dumps(PAYLOAD)}\n```"
    assert extract_json_object(text)["document_number"] == "SJ/2026/08/00142"


def test_reads_json_followed_by_chatter():
    """Model sering menambah kalimat penutup. Itu normal, bukan kegagalan."""
    text = json.dumps(PAYLOAD) + "\n\nSemoga membantu!"
    assert extract_json_object(text)["sender"] == "PT Sinar Terang"


def test_braces_inside_strings_do_not_break_balancing():
    payload = {"document_number": "SJ/{2026}/08", "items": []}
    assert extract_json_object(json.dumps(payload))["document_number"] == "SJ/{2026}/08"


def test_recovers_json_with_trailing_commas():
    text = (
        '{"document_number": "SJ/2026/08/00142", '
        '"items": [{"item_name": "Susu UHT", "quantity": 10,},],}'
    )
    res = extract_json_object(text)
    assert res is not None
    assert res["document_number"] == "SJ/2026/08/00142"
    assert len(res["items"]) == 1
    assert res["items"][0]["item_name"] == "Susu UHT"


def test_recovers_json_with_unquoted_values():
    """Model kadang mengeluarkan nilai seperti 'quantity_per_unit: 6 pcs' tanpa tanda kutip."""
    text = """{
        "document_type": "SURAT_JALAN",
        "document_number": "SJ-0017",
        "items": [
            {
                "item_name": "Minyak Goreng 2L",
                "quantity": 10,
                "unit_raw": "Karton",
                "quantity_per_unit": 6 pcs
            }
        ]
    }"""
    res = extract_json_object(text)
    assert res is not None
    assert res["document_number"] == "SJ-0017"
    assert len(res["items"]) == 1
    assert res["items"][0]["quantity_per_unit"] == "6 pcs"


def test_recovers_single_quoted_json():
    text = (
        "{'document_type': 'SURAT_JALAN', 'document_number': 'SJ-123', "
        "'items': [{'item_name': 'Kopi', 'quantity': 5, 'unit_raw': 'Dus'}]}"
    )
    res = extract_json_object(text)
    assert res is not None
    assert res["document_number"] == "SJ-123"
    assert res["items"][0]["item_name"] == "Kopi"


def test_recovers_truncated_json_missing_closing_brackets():
    text = (
        '{"document_type": "SURAT_JALAN", "document_number": "SJ-999", '
        '"items": [{"item_name": "Gula 1kg", "quantity": 20, "unit_raw": "Sak"}'
    )
    res = extract_json_object(text)
    assert res is not None
    assert res["document_number"] == "SJ-999"
    assert len(res["items"]) == 1
    assert res["items"][0]["item_name"] == "Gula 1kg"


def test_salvages_items_from_heavily_corrupted_payload():
    """Bila JSON luar hancur, baris barang individual dan nomor dokumen tetap diselamatkan."""
    text = """
    Berikut adalah data yang saya baca:
    "document_number": "SJ/CORRUPT/01",
    "document_type": "SURAT_JALAN",
    "items": [ CORRUPTED SYNTAX !!!
        {"item_name": "Beras Premium 5kg", "quantity": 50, "unit_raw": "Karung"},
        {"item_name": "Minyak SunCo 2L", "quantity": 25, "unit_raw": "Dus", "quantity_per_unit": 6}
    ] TAMBAHAN TEKS RUSAK
    """
    res = extract_json_object(text)
    assert res is not None
    assert res["document_number"] == "SJ/CORRUPT/01"
    assert len(res["items"]) == 2
    assert res["items"][0]["item_name"] == "Beras Premium 5kg"
    assert res["items"][1]["item_name"] == "Minyak SunCo 2L"


@pytest.mark.parametrize("text", ["", "tidak ada JSON di sini", "{ rusak", "[1, 2, 3]"])
def test_unparseable_output_returns_none_not_an_exception(text: str):
    assert extract_json_object(text) is None


# --------------------------------------------------------------------------
# Tanggal
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12 Agustus 2026", date(2026, 8, 12)),
        ("1 Januari 2026", date(2026, 1, 1)),
        ("31 Desember 2025", date(2025, 12, 31)),
        ("12-08-2026", date(2026, 8, 12)),
        ("12/08/2026", date(2026, 8, 12)),
        ("2026-08-12", date(2026, 8, 12)),
    ],
)
def test_parses_the_three_styles_the_dataset_prints(raw: str, expected: date):
    assert parse_indonesian_date(raw) == expected


def test_numeric_dates_are_day_first():
    """05/03/2026 di dokumen Indonesia berarti 5 Maret, bukan 3 Mei.

    Salah membaca ini menghasilkan tanggal yang tetap masuk akal — jenis bug
    yang lolos dari mata karena hasilnya tidak kelihatan aneh.
    """
    assert parse_indonesian_date("05/03/2026") == date(2026, 3, 5)


@pytest.mark.parametrize("raw", [None, "", "bukan tanggal", "32/13/2026"])
def test_unreadable_dates_become_none(raw):
    assert parse_indonesian_date(raw) is None


# --------------------------------------------------------------------------
# Angka & baris barang
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(12, 12), ("12", 12), ("1.200", 1200), ("1,200", 1200), (12.0, 12), ("12 pcs", 12)],
)
def test_coerces_numbers_written_in_document_style(raw, expected):
    assert coerce_int(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "banyak", True, {}])
def test_unusable_numbers_are_none(raw):
    assert coerce_int(raw) is None


def test_builds_an_item_and_derives_total_pieces():
    item = build_item(PAYLOAD["items"][0], source_page=1)

    assert item.item_name == "Susu UHT 250ml"
    assert item.quantity == 10
    assert item.unit_raw == "Karton"
    assert item.unit_normalized == UnitNormalized.KARTON
    assert item.quantity_per_unit == 12
    assert item.total_pieces == 120  # diturunkan oleh kontrak, bukan oleh model


def test_unusual_unit_keeps_raw_text_and_falls_back_to_unknown():
    item = build_item({"item_name": "Rokok", "quantity": 5, "unit_raw": "Slop"}, 1)

    assert item.unit_raw == "Slop"
    assert item.unit_normalized == UnitNormalized.UNKNOWN


@pytest.mark.parametrize(
    "row",
    [
        {"quantity": 5, "unit_raw": "Dus"},  # tanpa nama
        {"item_name": "Beras", "unit_raw": "Sak"},  # tanpa jumlah
        {"item_name": "Beras", "quantity": "banyak", "unit_raw": "Sak"},
        "bukan objek",
    ],
)
def test_half_read_rows_are_dropped(row):
    """Baris setengah terbaca dibuang, bukan ditebak.

    Baris karangan yang lolos akan dihitung Modul 2 sebagai barang nyata.
    """
    assert build_item(row, 1) is None


def test_accepts_indonesian_field_names():
    item = build_item({"nama_barang": "Gula", "jumlah": 3, "satuan": "Zak"}, 1)

    assert item.item_name == "Gula"
    assert item.unit_normalized == UnitNormalized.SAK


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------


def test_token_spans_track_character_offsets():
    spans = build_token_spans(["Susu", " UHT", " 250ml"], [0.9, 0.8, 0.7])

    assert [(s.start, s.end) for s in spans] == [(0, 4), (4, 8), (8, 14)]


def test_span_confidence_averages_overlapping_tokens():
    spans = [TokenSpan(0, 4, 1.0), TokenSpan(4, 8, 0.5), TokenSpan(8, 12, 0.0)]

    assert span_confidence(spans, 0, 8) == pytest.approx(0.75)
    assert span_confidence(spans, 0, 4) == pytest.approx(1.0)


def test_span_confidence_is_zero_when_nothing_matches():
    """Nol lebih jujur daripada angka tinggi yang tidak bisa ditelusuri."""
    spans = [TokenSpan(0, 4, 0.9)]

    assert span_confidence(spans, 10, 20) == 0.0
    assert span_confidence(spans, 5, 5) == 0.0


def test_confidence_for_value_locates_the_text():
    text = "SJ/2026/08/00142 lainnya"
    spans = build_token_spans(["SJ/2026/08/00142", " lainnya"], [0.95, 0.1])

    assert confidence_for_value(text, spans, "SJ/2026/08/00142") == pytest.approx(0.95)
    assert confidence_for_value(text, spans, "tidak ada") == 0.0


# --------------------------------------------------------------------------
# Halaman -> response
# --------------------------------------------------------------------------


def test_extract_page_reads_a_full_payload():
    page = extract_page(json.dumps(PAYLOAD), source_page=1)

    assert page.ok is True
    assert page.document_type == DocumentType.SURAT_JALAN
    assert page.document_date == date(2026, 8, 12)
    assert len(page.items) == 1
    assert page.items[0].source_page == 1


def test_extract_page_survives_garbage():
    page = extract_page("model bingung dan mengoceh", source_page=2)

    assert page.ok is False
    assert page.items == []


def test_assembled_response_satisfies_the_contract():
    page = extract_page(json.dumps(PAYLOAD), source_page=1)
    response = assemble_response(
        [page], page_count=1, truncated=False, total_pages=1, engine_name="x"
    )

    assert response.document_type == DocumentType.SURAT_JALAN
    assert response.page_count == 1
    assert len(response.confidence.items) == len(response.items)
    assert response.meta.engine == "x"
    assert response.meta.scenario is None


def test_confidence_items_stay_parallel_across_pages():
    """Kontrak mensyaratkan confidence.items sejajar dengan items."""
    first = extract_page(json.dumps(PAYLOAD), source_page=1)
    second = extract_page(json.dumps(PAYLOAD), source_page=2)
    response = assemble_response(
        [first, second], page_count=2, truncated=False, total_pages=2, engine_name="x"
    )

    assert len(response.items) == 2
    assert len(response.confidence.items) == 2


def test_document_fields_come_from_the_first_page_that_has_them():
    """Kop surat biasanya hanya di halaman pertama; barang tersebar."""
    blank = ExtractedPage(ok=True, raw_text="{}")
    filled = extract_page(json.dumps(PAYLOAD), source_page=2)
    response = assemble_response(
        [blank, filled], page_count=2, truncated=False, total_pages=2, engine_name="x"
    )

    assert response.document_number == "SJ/2026/08/00142"
    assert response.sender == "PT Sinar Terang"


def test_total_failure_returns_unknown_with_a_warning_not_an_exception():
    """Model yang gagal total tetap dijawab 200 + warnings, sesuai CONTRACT.md."""
    page = extract_page("tidak ada JSON", source_page=1)
    response = assemble_response(
        [page], page_count=1, truncated=False, total_pages=1, engine_name="x"
    )

    assert response.document_type == DocumentType.UNKNOWN
    assert any(warning.code == "UNRECOGNISED_DOCUMENT_TYPE" for warning in response.warnings)
    assert response.confidence.overall == 0.0


def test_truncation_is_reported_with_the_real_total():
    page = extract_page(json.dumps(PAYLOAD), source_page=1)
    response = assemble_response(
        [page], page_count=10, truncated=True, total_pages=14, engine_name="x"
    )

    truncation = [w for w in response.warnings if w.code == "PAGE_LIMIT_TRUNCATED"]
    assert len(truncation) == 1
    assert "14" in truncation[0].message


def test_low_confidence_threshold_comes_from_settings(monkeypatch):
    """Ambang 0.55 yang lama tidak pernah sekali pun menyala.

    Dari 165 baris terukur, skor terendah 0.842 — jadi LOW_CONFIDENCE_ITEM
    dijanjikan kontrak, digambar UI, dan dibaca Modul 3, tetapi mustahil
    muncul. Ambangnya kini dari config supaya bisa dikalibrasi ulang.
    """
    from app.core.config import get_settings
    from app.modules.document.extraction import low_confidence_threshold

    monkeypatch.setenv("AI_LOW_CONFIDENCE_THRESHOLD", "0.90")
    get_settings.cache_clear()
    assert low_confidence_threshold() == pytest.approx(0.90)
    get_settings.cache_clear()


def test_low_confidence_warning_follows_the_configured_threshold(monkeypatch):
    from app.core.config import get_settings

    # Satu token yang membentang seluruh teks: offset-nya harus sejajar dengan
    # raw_text, bukan dengan nama barangnya saja.
    raw = json.dumps(PAYLOAD)
    page = extract_page(raw, source_page=1, spans=build_token_spans([raw], [0.93]))

    monkeypatch.setenv("AI_LOW_CONFIDENCE_THRESHOLD", "0.95")
    get_settings.cache_clear()
    flagged = assemble_response(
        [page], page_count=1, truncated=False, total_pages=1, engine_name="x"
    )

    monkeypatch.setenv("AI_LOW_CONFIDENCE_THRESHOLD", "0.50")
    get_settings.cache_clear()
    quiet = assemble_response(
        [page], page_count=1, truncated=False, total_pages=1, engine_name="x"
    )
    get_settings.cache_clear()

    assert any(w.code == "LOW_CONFIDENCE_ITEM" for w in flagged.warnings)
    assert not any(w.code == "LOW_CONFIDENCE_ITEM" for w in quiet.warnings)


def test_min_confidence_exposes_a_weak_token_that_the_mean_hides():
    """Inti kandidat alternatif: satu token ragu di antara token yakin."""
    spans = build_token_spans(["Susu ", "UHT ", "250ml"], [0.99, 0.40, 0.99])

    assert span_confidence(spans, 0, 14) == pytest.approx(0.793, abs=0.01)
    assert span_confidence_min(spans, 0, 14) == pytest.approx(0.40)


def test_extract_page_records_the_alternative_confidences():
    spans = build_token_spans(["Susu UHT 250ml"], [0.9])
    page = extract_page(json.dumps(PAYLOAD), source_page=1, spans=spans)

    assert len(page.item_confidences_mean) == len(page.items)
    assert len(page.item_confidences_quantity) == len(page.items)


def test_contract_confidence_uses_the_weakest_token_not_the_average():
    """Rumus yang dipakai kontrak dipilih lewat pengukuran.

    Pada 845 baris, rata-rata hanya memisahkan baris benar dari salah sejauh
    4,4 poin; token terlemah memisahkan 18,2 poin. Test ini mengunci pilihan
    itu supaya tidak diam-diam berbalik.
    """
    raw = json.dumps(PAYLOAD)
    name = "Susu UHT 250ml"
    start = raw.index(name)

    # Satu token ragu di tengah nama, dikelilingi token yakin.
    spans = [
        TokenSpan(0, start, 0.99),
        TokenSpan(start, start + 4, 0.99),
        TokenSpan(start + 4, start + 9, 0.30),
        TokenSpan(start + 9, len(raw), 0.99),
    ]
    page = extract_page(raw, source_page=1, spans=spans)

    assert page.item_confidences[0] == pytest.approx(0.30)  # token terlemah
    assert page.item_confidences_mean[0] > 0.70  # rata-rata menyembunyikannya


def test_unusual_unit_raises_ambiguous_unit_warning():
    payload = dict(PAYLOAD, items=[{"item_name": "Rokok", "quantity": 5, "unit_raw": "Slop"}])
    page = extract_page(json.dumps(payload), source_page=1)
    response = assemble_response(
        [page], page_count=1, truncated=False, total_pages=1, engine_name="x"
    )

    assert any(warning.code == "AMBIGUOUS_UNIT" for warning in response.warnings)


def test_source_page_never_exceeds_page_count():
    """Validator kontrak menolak response yang melanggar ini."""
    page = extract_page(json.dumps(PAYLOAD), source_page=3)
    response = assemble_response(
        [page], page_count=3, truncated=False, total_pages=3, engine_name="x"
    )

    assert all(item.source_page <= response.page_count for item in response.items)
