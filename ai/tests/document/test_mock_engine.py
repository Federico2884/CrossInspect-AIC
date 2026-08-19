"""Test engine mock: 7 skenario, determinisme, dan sudut kontrak tiap skenario."""

import pytest

from app.modules.document.engines.base import DocumentPayload
from app.modules.document.engines.mock import SCENARIOS, MockEngine, resolve_scenario
from app.modules.document.schemas import DocumentType, ParseResponse, Severity, UnitNormalized

from .conftest import PDF_BYTES


def _payload(content: bytes = PDF_BYTES, scenario: str | None = None) -> DocumentPayload:
    return DocumentPayload(content=content, media_type="application/pdf", scenario=scenario)


def test_there_are_seven_scenarios():
    assert len(SCENARIOS) == 7
    assert len(set(SCENARIOS)) == 7


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_scenario_validates_against_the_contract(scenario):
    response = MockEngine().parse(_payload(scenario=scenario))
    assert isinstance(response, ParseResponse)
    assert response.meta.engine == "mock"
    assert response.meta.device == "cpu"
    assert response.meta.scenario == scenario
    # Round-trip lewat JSON: apa yang dilihat Laravel harus tetap valid.
    ParseResponse.model_validate(response.model_dump(mode="json"))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_same_input_yields_same_output(scenario):
    engine = MockEngine()
    first = engine.parse(_payload(scenario=scenario)).model_dump(mode="json")
    second = engine.parse(_payload(scenario=scenario)).model_dump(mode="json")
    assert first == second


def test_scenario_falls_back_to_content_hash():
    chosen = resolve_scenario(_payload())
    assert chosen in SCENARIOS
    assert resolve_scenario(_payload()) == chosen  # stabil untuk isi yang sama


def test_different_content_can_select_different_scenarios():
    picks = {resolve_scenario(_payload(content=b"%PDF-" + bytes([i]))) for i in range(64)}
    assert len(picks) > 1  # hash benar-benar menyebar, bukan konstanta


def test_explicit_scenario_wins_over_hash():
    assert resolve_scenario(_payload(scenario="invoice")) == "invoice"


def test_multi_page_spreads_items_across_pages():
    response = MockEngine().parse(_payload(scenario="multi_page"))
    assert response.page_count == 3
    assert sorted(item.source_page for item in response.items) == [1, 2, 3]


def test_mixed_units_keeps_carton_count_separate_from_pieces():
    response = MockEngine().parse(_payload(scenario="mixed_units"))
    susu = response.items[0]
    assert (susu.quantity, susu.quantity_per_unit, susu.total_pieces) == (10, 12, 120)

    # Satuan di luar enum tetap terbaca mentahnya dan memicu warning.
    tisu = response.items[2]
    assert tisu.unit_raw == "Ball"
    assert tisu.unit_normalized is UnitNormalized.UNKNOWN
    assert any(warning.item_index == 2 for warning in response.warnings)


def test_low_confidence_flags_items_individually():
    response = MockEngine().parse(_payload(scenario="low_confidence"))
    assert response.confidence.overall < 0.5
    flagged = [w.item_index for w in response.warnings if w.item_index is not None]
    assert flagged == [0, 1]


def test_missing_fields_returns_nulls_with_warnings_not_an_error():
    response = MockEngine().parse(_payload(scenario="missing_fields"))
    assert response.document_date is None
    assert response.sender is None
    assert {warning.code for warning in response.warnings} >= {"MISSING_DOCUMENT_DATE"}


def test_unknown_type_reports_error_severity_but_still_parses():
    response = MockEngine().parse(_payload(scenario="unknown_type"))
    assert response.document_type is DocumentType.UNKNOWN
    assert response.items == []
    assert any(warning.severity is Severity.ERROR for warning in response.warnings)
