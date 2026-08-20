"""Test kontrak: aturan yang harus tetap benar apa pun engine-nya."""

import pytest
from pydantic import ValidationError

from app.modules.document.schemas import (
    Confidence,
    DocumentType,
    Item,
    Meta,
    ParseResponse,
    UnitNormalized,
)


def _item(**overrides) -> Item:
    base = {"item_name": "Indomie Goreng", "quantity": 10, "unit_raw": "Karton"}
    return Item(**{**base, **overrides})


def test_total_pieces_derived_from_quantity_per_unit():
    # '10 karton @ 12 pcs' -> cross-check membandingkan 10, bukan 120.
    item = _item(quantity=10, quantity_per_unit=12)
    assert item.quantity == 10
    assert item.total_pieces == 120


def test_total_pieces_stays_none_without_quantity_per_unit():
    assert _item().total_pieces is None


def test_explicit_total_pieces_is_not_overwritten():
    # Dokumen kadang mencantumkan total sendiri; nilai eksplisit menang.
    assert _item(quantity=10, quantity_per_unit=12, total_pieces=118).total_pieces == 118


def test_unit_raw_survives_when_normalisation_fails():
    item = _item(unit_raw="Ball", unit_normalized=UnitNormalized.UNKNOWN)
    assert item.unit_raw == "Ball"
    assert item.unit_normalized is UnitNormalized.UNKNOWN


def test_unknown_normalized_unit_is_rejected():
    with pytest.raises(ValidationError):
        _item(unit_normalized="ball")


def test_negative_quantity_is_rejected():
    with pytest.raises(ValidationError):
        _item(quantity=-1)


def test_confidence_outside_range_is_rejected():
    with pytest.raises(ValidationError):
        Confidence(document_number=1.5, items=[], overall=0.5)

    with pytest.raises(ValidationError):
        Confidence(document_number=0.9, items=[0.5, 1.2], overall=0.5)


def _response(**overrides) -> ParseResponse:
    base = {
        "document_type": DocumentType.SURAT_JALAN,
        "document_number": "SJ/2026/08/00142",
        "confidence": Confidence(document_number=0.9, items=[], overall=0.9),
        "meta": Meta(engine="mock", processing_ms=1),
    }
    return ParseResponse(**{**base, **overrides})


def test_source_page_beyond_page_count_is_rejected():
    with pytest.raises(ValidationError):
        _response(page_count=1, items=[_item(source_page=3)])


def test_document_date_serialises_as_iso_string():
    payload = _response(document_date="2026-08-12").model_dump(mode="json")
    assert payload["document_date"] == "2026-08-12"


def test_document_date_accepts_null():
    assert _response().document_date is None


def test_device_is_always_cpu():
    assert Meta(engine="mock", processing_ms=0).device == "cpu"

    with pytest.raises(ValidationError):
        Meta(engine="mock", processing_ms=0, device="cuda")


def test_unexpected_field_is_rejected():
    # extra="forbid" menjaga kontrak tidak melar diam-diam.
    with pytest.raises(ValidationError):
        _response(unexpected_field="nope")
