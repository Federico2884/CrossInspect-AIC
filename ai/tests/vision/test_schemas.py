"""Test kontrak Modul 2: aturan yang harus tetap benar apa pun engine-nya."""

import pytest
from pydantic import ValidationError

from app.modules.vision.schemas import (
    BBox,
    CountConfidence,
    DefectFinding,
    DefectReport,
    DefectStatus,
    Detection,
    InspectResponse,
    InspectWarning,
    Meta,
)


def _bbox(x1=0.1, y1=0.1, x2=0.4, y2=0.4) -> BBox:
    return BBox(x1=x1, y1=y1, x2=x2, y2=y2)


def _detection(class_name="cardboard", confidence=0.9) -> Detection:
    return Detection(class_name=class_name, confidence=confidence, bbox=_bbox())


def _meta(**overrides) -> Meta:
    base = {
        "engine": "mock",
        "processing_ms": 0,
        "conf_threshold": 0.4,
        "image_width": 1280,
        "image_height": 960,
    }
    return Meta(**{**base, **overrides})


def _response(detections, class_counts=None, warnings=None, **overrides) -> InspectResponse:
    base = {
        "detected_count": len(detections),
        "class_counts": class_counts
        if class_counts is not None
        else ({"cardboard": len(detections)} if detections else {}),
        "detections": detections,
        "count_confidence": CountConfidence(mean_detection=0.9, min_detection=0.9, overall=0.9),
        "warnings": warnings or [],
        "meta": _meta(),
    }
    return InspectResponse(**{**base, **overrides})


def test_bbox_rejects_inverted_coordinates():
    with pytest.raises(ValidationError):
        BBox(x1=0.5, y1=0.1, x2=0.2, y2=0.4)


def test_bbox_rejects_zero_area():
    with pytest.raises(ValidationError):
        BBox(x1=0.3, y1=0.3, x2=0.3, y2=0.6)


def test_bbox_rejects_coordinates_outside_unit_square():
    # Ternormalisasi: nilai piksel yang lupa dibagi akan tertangkap di sini.
    with pytest.raises(ValidationError):
        BBox(x1=0.0, y1=0.0, x2=1280.0, y2=960.0)


def test_detected_count_must_match_detections_length():
    with pytest.raises(ValidationError):
        _response([_detection()], detected_count=5)


def test_class_counts_must_sum_to_detected_count():
    with pytest.raises(ValidationError):
        _response([_detection(), _detection()], class_counts={"cardboard": 1})


def test_multi_class_counts_are_accepted():
    # Model hari ini satu kelas, tetapi kontrak sudah siap untuk training ulang
    # yang menambah kelas — ini yang menjaga janji itu.
    detections = [_detection("cardboard"), _detection("damaged_box")]
    response = _response(detections, class_counts={"cardboard": 1, "damaged_box": 1})
    assert response.detected_count == 2
    assert response.class_counts["damaged_box"] == 1


def test_warning_cannot_point_to_missing_detection():
    warning = InspectWarning(code="LOW_CONFIDENCE_DETECTION", message="x", detection_index=3)
    with pytest.raises(ValidationError):
        _response([_detection()], warnings=[warning])


def test_defect_findings_forbidden_while_unavailable():
    # Penjaga utama kejujuran MVP: tidak ada yang boleh mengarang temuan cacat
    # selama modelnya belum ada.
    with pytest.raises(ValidationError):
        DefectReport(
            status=DefectStatus.UNAVAILABLE,
            findings=[DefectFinding(label="penyok", confidence=0.8)],
        )


def test_defect_suspected_requires_at_least_one_finding():
    with pytest.raises(ValidationError):
        DefectReport(status=DefectStatus.DEFECT_SUSPECTED, findings=[])


def test_defect_defaults_to_unavailable():
    assert DefectReport().status is DefectStatus.UNAVAILABLE


def test_empty_response_is_valid():
    response = _response([])
    assert response.detected_count == 0
    assert response.class_counts == {}


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        _response([], unexpected_field="x")
