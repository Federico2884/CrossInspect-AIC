"""Test penilaian dan agregasi.

Yang dijaga terutama satu hal: kesalahan pada satu field tidak boleh mencemari
angka field lain. Tanpa itu, temuan seperti "nama benar 8/10 tapi jumlah benar
2/10" akan terlebur jadi satu angka dan hilang.
"""

from datetime import date

import pytest

from app.modules.document.schemas import (
    Confidence,
    DocumentType,
    Item,
    Meta,
    ParseResponse,
    UnitNormalized,
)
from scripts.evaluation.metrics import aggregate, group_by, score_document
from scripts.synthetic.document import GroundTruth


def make_item(name="Susu UHT 250ml", quantity=10, unit_raw="Karton", per_unit=12, page=1):
    return Item(
        item_name=name,
        sku="ULT-250",
        quantity=quantity,
        unit_raw=unit_raw,
        unit_normalized=UnitNormalized.KARTON,
        quantity_per_unit=per_unit,
        source_page=page,
    )


def make_truth(items=None):
    return GroundTruth(
        doc_id="sj_0001",
        document_type=DocumentType.SURAT_JALAN,
        document_number="SJ/2026/08/00142",
        document_date=date(2026, 8, 12),
        sender="PT Sinar Terang",
        recipient="Toko Maju",
        page_count=1,
        items=items if items is not None else [make_item()],
    )


def make_response(items=None, confidences=None, **overrides):
    items = items if items is not None else [make_item()]
    payload = dict(
        document_type=DocumentType.SURAT_JALAN,
        document_number="SJ/2026/08/00142",
        document_date=date(2026, 8, 12),
        sender="PT Sinar Terang",
        recipient="Toko Maju",
        page_count=1,
        items=items,
        confidence=Confidence(
            document_number=0.9,
            items=confidences if confidences is not None else [0.9] * len(items),
            overall=0.9,
        ),
        meta=Meta(engine="test", device="cpu", processing_ms=1),
    )
    payload.update(overrides)
    return ParseResponse(**payload)


def score(truth, response, **kwargs):
    options = dict(
        doc_id="sj_0001",
        source="pdf",
        page=None,
        severity=None,
        layout="classic",
        engine="test",
        latency_s=1.0,
        truth=truth,
        response=response,
        truth_items=list(truth.items),
        score_header=True,
    )
    options.update(kwargs)
    return score_document(**options)


def test_perfect_document_scores_full_marks():
    result = score(make_truth(), make_response())

    assert result.parsed is True
    assert result.rows_matched == 1
    assert result.rows_exact_name == 1
    assert result.quantity_ok == 1
    assert result.unit_raw_ok == 1
    assert result.document_number_ok is True
    assert result.document_date_ok is True
    assert result.page_count_ok is True


def test_wrong_quantity_only_hurts_the_quantity_metric():
    """Bentuk temuan sj_0043: barisnya ketemu, jumlahnya yang salah."""
    result = score(make_truth(), make_response([make_item(quantity=99)]))

    assert result.rows_matched == 1  # barisnya tetap ketemu
    assert result.rows_exact_name == 1  # namanya tetap benar
    assert result.quantity_ok == 0  # hanya ini yang jatuh
    assert result.unit_raw_ok == 1


def test_slightly_different_name_matches_but_is_not_exact():
    result = score(make_truth(), make_response([make_item(name="Susu UHT 250 ml")]))

    assert result.rows_matched == 1
    assert result.rows_exact_name == 0
    assert result.quantity_ok == 1


def test_document_number_comparison_ignores_case_and_padding():
    response = make_response(document_number="  sj/2026/08/00142 ")

    assert score(make_truth(), response).document_number_ok is True


def test_party_names_tolerate_small_spelling_differences():
    """Nama pihak adalah prosa bebas; ejaan persis terlalu kejam."""
    response = make_response(sender="PT Sinar Terangg")

    assert score(make_truth(), response).sender_ok is True


def test_very_different_party_name_is_wrong():
    response = make_response(sender="CV Lain Sama Sekali")

    assert score(make_truth(), response).sender_ok is False


def test_empty_response_scores_zero_without_raising():
    response = make_response(items=[], confidences=[], document_number="")
    result = score(make_truth(), response)

    assert result.parsed is False
    assert result.rows_matched == 0
    assert result.quantity_ok == 0
    assert result.document_number_ok is False


def test_header_can_be_skipped_for_later_photo_pages():
    """Kop surat hanya ada di halaman pertama; halaman 2 tidak boleh dihukum."""
    result = score(make_truth(), make_response(), score_header=False)

    assert result.document_number_ok is None
    assert result.document_date_ok is None
    assert result.rows_matched == 1  # baris tetap dinilai


def test_page_count_is_not_scored_for_a_single_page_photo():
    """Satu foto memang satu halaman, walau dokumennya dua halaman.

    Menilainya di sana mengukur cara harness memotong dokumen, bukan model.
    """
    truth = make_truth()
    truth.page_count = 2
    response = make_response()  # page_count=1, benar untuk satu foto

    photo = score(truth, response, source="image", page=1, score_page_count=False)
    pdf = score(truth, response, source="pdf")

    assert photo.page_count_ok is None  # tidak dinilai
    assert photo.document_number_ok is True  # field kop lain tetap dinilai
    assert pdf.page_count_ok is False  # untuk PDF utuh, 1 != 2 memang salah


def test_confidence_pairs_record_whether_the_row_was_right():
    right = score(make_truth(), make_response(confidences=[0.95]))
    wrong = score(make_truth(), make_response([make_item(quantity=99)], confidences=[0.3]))

    assert right.confidence_pairs == [(0.95, True)]
    assert wrong.confidence_pairs == [(0.3, False)]


# --------------------------------------------------------------------------
# Agregasi
# --------------------------------------------------------------------------


def test_aggregate_divides_field_accuracy_by_matched_rows():
    truth = make_truth([make_item(name="A satu"), make_item(name="B dua")])
    response = make_response(
        [make_item(name="A satu"), make_item(name="B dua", quantity=99)],
        confidences=[0.9, 0.4],
    )
    bucket = aggregate([score(truth, response, truth_items=list(truth.items))])

    assert bucket.recall == 1.0
    assert bucket.field_rate("quantity_ok") == 0.5  # 1 dari 2 baris terjodoh
    assert bucket.field_rate("unit_raw_ok") == 1.0


def test_aggregate_recall_and_precision_use_the_right_denominators():
    truth = make_truth([make_item(name="A satu"), make_item(name="B dua")])
    response = make_response([make_item(name="A satu")], confidences=[0.9])
    bucket = aggregate([score(truth, response, truth_items=list(truth.items))])

    assert bucket.recall == 0.5
    assert bucket.precision == 1.0


def test_confidence_split_separates_correct_from_wrong():
    truth = make_truth([make_item(name="A satu"), make_item(name="B dua")])
    response = make_response(
        [make_item(name="A satu"), make_item(name="B dua", quantity=99)],
        confidences=[0.9, 0.2],
    )
    bucket = aggregate([score(truth, response, truth_items=list(truth.items))])
    correct, wrong, n_correct, n_wrong = bucket.confidence_split

    assert correct == pytest.approx(0.9)
    assert wrong == pytest.approx(0.2)
    assert (n_correct, n_wrong) == (1, 1)


def test_group_by_splits_and_labels_missing_values():
    clean = score(make_truth(), make_response())
    photo = score(make_truth(), make_response(), source="image", severity="heavy")
    groups = group_by([clean, photo], "severity")

    assert set(groups) == {"—", "heavy"}
    assert groups["heavy"].documents == 1


def test_empty_aggregate_reports_none_not_a_crash():
    bucket = aggregate([])

    assert bucket.recall is None
    assert bucket.parse_rate is None
    assert bucket.field_rate("quantity_ok") is None
