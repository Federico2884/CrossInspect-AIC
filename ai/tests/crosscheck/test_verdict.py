"""Aturan vonis Modul 3, sesuai urutan di CONTRACT.md."""

import pytest
from pydantic import ValidationError

from app.modules.crosscheck import warnings as w
from app.modules.crosscheck.schemas import (
    CrossCheckRequest,
    CrossCheckResponse,
    CrossCheckStatus,
    ExclusionReason,
    Meta,
    ParameterReport,
    ParameterStatus,
    QuantityReport,
)
from app.modules.crosscheck.service import cross_check
from app.modules.document import schemas as doc
from app.modules.document.warnings import LOW_CONFIDENCE_ITEM
from app.modules.vision.warnings import COUNT_UNRELIABLE, NO_OBJECT_DETECTED, POSSIBLE_OCCLUSION
from tests.crosscheck.conftest import (
    doc_warning,
    item,
    make_document,
    make_vision,
    vis_warning,
)


def run(document=None, vision=None) -> CrossCheckResponse:
    return cross_check(
        CrossCheckRequest(
            document=document if document is not None else make_document(),
            vision=vision if vision is not None else make_vision(),
        )
    )


def codes(response: CrossCheckResponse) -> set[str]:
    return {warning.code for warning in response.warnings}


# --- Urutan vonis ------------------------------------------------------------


def test_match_when_everything_lines_up():
    result = run(make_document([item(quantity=10)]), make_vision(detected_count=10))
    assert result.status is CrossCheckStatus.MATCH
    assert result.quantity.difference == 0
    assert result.quantity.excluded_items == []


def test_mismatch_reports_the_shortfall():
    result = run(make_document([item(quantity=10)]), make_vision(detected_count=8))
    assert result.status is CrossCheckStatus.MISMATCH
    assert result.quantity.document_total == 10
    assert result.quantity.detected_total == 8
    assert result.quantity.difference == -2


def test_partial_when_a_row_cannot_be_checked():
    document = make_document(
        [
            item(quantity=10),
            item(name="Gula Pasir", quantity=50, unit_raw="Kg", unit=doc.UnitNormalized.KG),
        ]
    )
    result = run(document, make_vision(detected_count=10))

    assert result.status is CrossCheckStatus.PARTIAL
    # Baris kg tidak boleh mencemari total dokumen.
    assert result.quantity.document_total == 10
    assert len(result.quantity.excluded_items) == 1
    assert result.quantity.excluded_items[0].reason is ExclusionReason.UNIT_IS_WEIGHT
    assert w.PARTIAL_COVERAGE in codes(result)


def test_unverifiable_when_vision_distrusts_its_own_count():
    """Aturan pertama menang: hitungan yang tidak dipercaya tidak memvonis apa pun,
    walaupun angkanya kebetulan berbeda."""
    result = run(
        make_document([item(quantity=10)]),
        make_vision(detected_count=3, warnings=[vis_warning(COUNT_UNRELIABLE)]),
    )
    assert result.status is CrossCheckStatus.UNVERIFIABLE
    assert w.COUNT_UNRELIABLE_UPSTREAM in codes(result)


def test_unverifiable_when_no_row_is_cardboard():
    document = make_document(
        [item(name="Gula Pasir", quantity=50, unit_raw="Kg", unit=doc.UnitNormalized.KG)]
    )
    result = run(document, make_vision(detected_count=0))

    assert result.status is CrossCheckStatus.UNVERIFIABLE
    assert w.NO_COUNTABLE_ITEMS in codes(result)
    assert result.quantity.document_total == 0


def test_unreliable_count_outranks_a_real_mismatch():
    """Kalau dua aturan sama-sama berlaku, yang di atas menang."""
    result = run(
        make_document([item(quantity=10)]),
        make_vision(detected_count=2, warnings=[vis_warning(COUNT_UNRELIABLE)]),
    )
    assert result.status is not CrossCheckStatus.MISMATCH


# --- Aritmetika yang paling gampang salah ------------------------------------


def test_compares_quantity_not_total_pieces():
    """10 karton @ 12 pcs dibandingkan dengan 10, bukan 120.

    Kamera hanya melihat kemasan terluar; isi kardus tersegel tidak terlihat.
    Salah memilih field di sini melaporkan kekurangan 110 barang pada kiriman
    yang sebenarnya utuh.
    """
    document = make_document([item(quantity=10, quantity_per_unit=12)])
    assert document.items[0].total_pieces == 120

    result = run(document, make_vision(detected_count=10))

    assert result.status is CrossCheckStatus.MATCH
    assert result.quantity.document_total == 10


def test_sums_only_cardboard_rows_across_a_mixed_document():
    document = make_document(
        [
            item(name="Susu", quantity=10, unit_raw="Karton", unit=doc.UnitNormalized.KARTON),
            item(name="Teh", quantity=5, unit_raw="Dus", unit=doc.UnitNormalized.BOX),
            item(name="Kopi", quantity=2, unit_raw="Koli", unit=doc.UnitNormalized.KOLI),
            item(name="Gula", quantity=50, unit_raw="Kg", unit=doc.UnitNormalized.KG),
            item(name="Tali", quantity=3, unit_raw="Gulung", unit=doc.UnitNormalized.ROLL),
        ]
    )
    result = run(document, make_vision(detected_count=17))

    assert result.quantity.document_total == 17  # 10 + 5 + 2
    assert len(result.quantity.counted_items) == 3
    assert len(result.quantity.excluded_items) == 2
    assert result.status is CrossCheckStatus.PARTIAL


# --- Occlusion ---------------------------------------------------------------


def test_occlusion_explains_a_shortfall_without_hiding_it():
    result = run(
        make_document([item(quantity=10)]),
        make_vision(detected_count=7, warnings=[vis_warning(POSSIBLE_OCCLUSION)]),
    )
    # Selisih tetap dilaporkan — occlusion menjelaskan, bukan membuktikan utuh.
    assert result.status is CrossCheckStatus.MISMATCH
    assert w.COUNT_POSSIBLY_UNDERSTATED in codes(result)


def test_occlusion_does_not_excuse_a_surplus():
    """Kotak terhalang membuat hitungan lebih rendah, tidak pernah lebih tinggi."""
    result = run(
        make_document([item(quantity=10)]),
        make_vision(detected_count=13, warnings=[vis_warning(POSSIBLE_OCCLUSION)]),
    )
    assert result.status is CrossCheckStatus.MISMATCH
    assert w.COUNT_POSSIBLY_UNDERSTATED not in codes(result)


# --- Parameter yang belum terjawab -------------------------------------------


def test_identity_and_integrity_are_always_declared_unavailable():
    result = run()

    assert result.identity.status is ParameterStatus.UNAVAILABLE
    assert result.identity.reason
    assert result.integrity.status is ParameterStatus.UNAVAILABLE
    assert result.integrity.reason
    assert {w.IDENTITY_NOT_VERIFIED, w.INTEGRITY_NOT_VERIFIED} <= codes(result)


def test_integrity_follows_module_two_once_a_defect_model_exists():
    from app.modules.vision.schemas import DefectStatus

    clean = run(vision=make_vision(defect_status=DefectStatus.CLEAN))
    assert clean.integrity.status is ParameterStatus.VERIFIED
    assert w.INTEGRITY_NOT_VERIFIED not in codes(clean)


# --- Sinyal dari hulu --------------------------------------------------------


def test_low_confidence_on_a_counted_row_is_surfaced():
    document = make_document(
        [item(quantity=10)], warnings=[doc_warning(LOW_CONFIDENCE_ITEM, item_index=0)]
    )
    result = run(document, make_vision(detected_count=10))
    assert w.DOCUMENT_LOW_CONFIDENCE in codes(result)


def test_low_confidence_on_an_excluded_row_is_not_surfaced():
    """Baris itu tidak ikut dijumlahkan, jadi keraguannya tidak memengaruhi vonis."""
    document = make_document(
        [
            item(quantity=10),
            item(name="Gula", quantity=50, unit_raw="Kg", unit=doc.UnitNormalized.KG),
        ],
        warnings=[doc_warning(LOW_CONFIDENCE_ITEM, item_index=1)],
    )
    result = run(document, make_vision(detected_count=10))
    assert w.DOCUMENT_LOW_CONFIDENCE not in codes(result)


def test_unknown_document_type_is_flagged():
    document = make_document(document_type=doc.DocumentType.UNKNOWN)
    assert w.DOCUMENT_TYPE_UNKNOWN in codes(run(document, make_vision(detected_count=10)))


def test_empty_photo_is_flagged():
    result = run(
        make_document([item(quantity=10)]),
        make_vision(detected_count=0, warnings=[vis_warning(NO_OBJECT_DETECTED)]),
    )
    assert w.NO_OBJECT_DETECTED_UPSTREAM in codes(result)
    assert result.status is CrossCheckStatus.MISMATCH


def test_meta_records_which_engines_produced_the_inputs():
    result = run(make_document(engine="qwen2vl"), make_vision(engine="yolo"))
    assert result.meta.document_engine == "qwen2vl"
    assert result.meta.vision_engine == "yolo"
    assert result.meta.engine == "rules"


# --- Penjagaan schema --------------------------------------------------------


def test_schema_refuses_match_when_rows_were_excluded():
    """Penjagaan terakhir: 'cocok' tidak boleh keluar kalau ada yang tak diperiksa."""
    with pytest.raises(ValidationError, match="PARTIAL"):
        CrossCheckResponse(
            status=CrossCheckStatus.MATCH,
            quantity=QuantityReport(
                document_total=10,
                detected_total=10,
                difference=0,
                excluded_items=[
                    {
                        "item_index": 1,
                        "item_name": "Gula",
                        "quantity": 50,
                        "unit_raw": "Kg",
                        "unit_normalized": "kg",
                        "reason": "UNIT_IS_WEIGHT",
                    }
                ],
            ),
            identity=ParameterReport(reason="…"),
            integrity=ParameterReport(reason="…"),
            meta=Meta(processing_ms=1, document_engine="mock", vision_engine="mock"),
        )


def test_schema_refuses_inconsistent_arithmetic():
    with pytest.raises(ValidationError, match="difference"):
        QuantityReport(document_total=10, detected_total=8, difference=99)


def test_schema_refuses_unavailable_without_a_reason():
    with pytest.raises(ValidationError, match="reason"):
        ParameterReport(status=ParameterStatus.UNAVAILABLE)
