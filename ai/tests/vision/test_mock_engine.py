"""Test engine mock Modul 2: determinisme dan cakupan skenario."""

import pytest

from app.modules.vision.engines.base import ImagePayload
from app.modules.vision.engines.mock import SCENARIOS, MockEngine, pick_scenario
from app.modules.vision.schemas import DefectStatus, Severity
from app.modules.vision.warnings import (
    COUNT_UNRELIABLE,
    DEFECT_CHECK_UNAVAILABLE,
    NO_OBJECT_DETECTED,
    POSSIBLE_OCCLUSION,
)

from .conftest import PNG_BYTES


def _payload(scenario=None, content=PNG_BYTES, width=1280, height=960) -> ImagePayload:
    return ImagePayload(
        content=content,
        media_type="image/png",
        width=width,
        height=height,
        filename="tumpukan.png",
        scenario=scenario,
    )


def _codes(response) -> set[str]:
    return {warning.code for warning in response.warnings}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_scenario_produces_a_valid_response(scenario):
    response = MockEngine().inspect(_payload(scenario))
    assert response.meta.scenario == scenario
    assert response.detected_count == len(response.detections)
    assert sum(response.class_counts.values()) == response.detected_count


def test_same_bytes_always_pick_the_same_scenario():
    # Determinisme adalah alasan mock ini ada: klien Laravel butuh response
    # yang stabil untuk dikembangkan.
    first = pick_scenario(_payload())
    for _ in range(5):
        assert pick_scenario(_payload()) == first


def test_different_bytes_can_pick_different_scenarios():
    picks = {pick_scenario(_payload(content=bytes([index]) * 32)) for index in range(60)}
    assert len(picks) > 1


def test_defect_is_always_reported_unavailable():
    for scenario in SCENARIOS:
        response = MockEngine().inspect(_payload(scenario))
        assert response.defect.status is DefectStatus.UNAVAILABLE
        assert response.defect.findings == []
        assert DEFECT_CHECK_UNAVAILABLE in _codes(response)


def test_empty_scenario_reports_no_object_at_error_severity():
    response = MockEngine().inspect(_payload("empty"))
    assert response.detected_count == 0
    assert response.count_confidence.overall == 0.0
    severities = {w.code: w.severity for w in response.warnings}
    assert severities[NO_OBJECT_DETECTED] is Severity.ERROR


def test_occlusion_scenarios_flag_undercount_risk():
    # Recall model masih terbatas; tumpukan bertindihan harus menurunkan
    # kelayakan percaya, bukan dilaporkan sebagai hitungan pasti.
    for scenario in ("partial_occlusion", "crowded"):
        response = MockEngine().inspect(_payload(scenario))
        assert POSSIBLE_OCCLUSION in _codes(response)
        assert response.count_confidence.overall < response.count_confidence.mean_detection


def test_low_confidence_scenario_marks_the_count_unreliable():
    response = MockEngine().inspect(_payload("low_confidence"))
    assert COUNT_UNRELIABLE in _codes(response)
    assert response.count_confidence.mean_detection < 0.5


def test_bboxes_stay_inside_the_image():
    for scenario in SCENARIOS:
        for detection in MockEngine().inspect(_payload(scenario)).detections:
            box = detection.bbox
            assert 0.0 <= box.x1 < box.x2 <= 1.0
            assert 0.0 <= box.y1 < box.y2 <= 1.0


def test_meta_echoes_the_real_image_dimensions():
    response = MockEngine().inspect(_payload("clean_stack", width=4032, height=3024))
    assert (response.meta.image_width, response.meta.image_height) == (4032, 3024)
