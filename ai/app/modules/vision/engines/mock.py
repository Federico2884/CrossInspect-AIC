"""Engine mock Modul 2 — 7 skenario deterministik.

Tujuannya bukan mensimulasikan YOLO, melainkan mengunci kontrak: setiap skenario
menekan satu sudut yang harus tetap benar saat model asli masuk (tumpukan
tertutup sebagian, confidence rendah, foto kosong, resolusi buruk). Tidak ada
import torch di jalur ini — image slim harus bisa melayaninya.
"""

from __future__ import annotations

import hashlib
import math

from app.modules.vision import warnings as w
from app.modules.vision.engines.base import ImagePayload
from app.modules.vision.schemas import (
    BBox,
    CountConfidence,
    DefectReport,
    DefectStatus,
    Detection,
    InspectResponse,
    Meta,
    Severity,
)

ENGINE_NAME = "mock"

# Kelas yang dipakai model nyata sekarang. Mock memakai nama yang sama supaya
# klien tidak melihat kosakata berbeda antara mock dan YOLO.
MOCK_CLASS = "cardboard"

MOCK_CONF_THRESHOLD = 0.40

SCENARIOS: tuple[str, ...] = (
    "clean_stack",
    "partial_occlusion",
    "single_item",
    "crowded",
    "low_confidence",
    "empty",
    "low_resolution",
)


def _grid_boxes(count: int, overlap: float = 0.0) -> list[BBox]:
    """Susun ``count`` kotak dalam grid ternormalisasi.

    ``overlap`` > 0 menggeser tiap kotak agar bertindihan dengan tetangganya —
    itulah cara skenario occlusion dibuat tanpa perlu gambar sungguhan.
    """
    if count <= 0:
        return []

    cols = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / cols))
    cell_w, cell_h = 1.0 / cols, 1.0 / rows
    margin = 0.12 * min(cell_w, cell_h)

    boxes: list[BBox] = []
    for index in range(count):
        row, col = divmod(index, cols)
        x1 = col * cell_w + margin
        y1 = row * cell_h + margin
        x2 = (col + 1) * cell_w - margin + overlap * cell_w
        y2 = (row + 1) * cell_h - margin + overlap * cell_h
        boxes.append(
            BBox(
                x1=round(x1, 4),
                y1=round(y1, 4),
                x2=round(min(x2, 1.0), 4),
                y2=round(min(y2, 1.0), 4),
            )
        )
    return boxes


def _detections(confidences: list[float], overlap: float = 0.0) -> list[Detection]:
    boxes = _grid_boxes(len(confidences), overlap=overlap)
    return [
        Detection(class_name=MOCK_CLASS, confidence=conf, bbox=box)
        for conf, box in zip(confidences, boxes, strict=True)
    ]


def _confidence(confidences: list[float], penalty: float = 0.0) -> CountConfidence:
    if not confidences:
        return CountConfidence(mean_detection=0.0, min_detection=0.0, overall=0.0)
    mean = sum(confidences) / len(confidences)
    return CountConfidence(
        mean_detection=round(mean, 4),
        min_detection=round(min(confidences), 4),
        overall=round(max(0.0, mean - penalty), 4),
    )


def _meta(scenario: str, payload: ImagePayload) -> Meta:
    # processing_ms diisi service setelah pekerjaan selesai.
    return Meta(
        engine=ENGINE_NAME,
        device="cpu",
        processing_ms=0,
        model=None,
        conf_threshold=MOCK_CONF_THRESHOLD,
        image_width=payload.width,
        image_height=payload.height,
        scenario=scenario,
    )


def _response(
    scenario: str,
    payload: ImagePayload,
    confidences: list[float],
    extra_warnings: list,
    overlap: float = 0.0,
    penalty: float = 0.0,
) -> InspectResponse:
    detections = _detections(confidences, overlap=overlap)
    return InspectResponse(
        detected_count=len(detections),
        class_counts={MOCK_CLASS: len(detections)} if detections else {},
        detections=detections,
        count_confidence=_confidence(confidences, penalty=penalty),
        defect=DefectReport(status=DefectStatus.UNAVAILABLE),
        warnings=[w.defect_unavailable(), *extra_warnings],
        meta=_meta(scenario, payload),
    )


def _clean_stack(payload: ImagePayload) -> InspectResponse:
    confidences = [0.91, 0.89, 0.88, 0.87, 0.86, 0.85, 0.84, 0.83, 0.82, 0.81, 0.80, 0.79]
    return _response("clean_stack", payload, confidences, [])


def _partial_occlusion(payload: ImagePayload) -> InspectResponse:
    confidences = [0.88, 0.84, 0.79, 0.71, 0.66, 0.61, 0.55]
    extra = [
        w.warning(
            w.POSSIBLE_OCCLUSION,
            "Kotak saling bertindihan; sebagian kemasan kemungkinan tertutup dan tidak terhitung.",
        )
    ]
    return _response("partial_occlusion", payload, confidences, extra, overlap=0.35, penalty=0.15)


def _single_item(payload: ImagePayload) -> InspectResponse:
    return _response("single_item", payload, [0.93], [])


def _crowded(payload: ImagePayload) -> InspectResponse:
    confidences = [round(0.86 - index * 0.012, 4) for index in range(30)]
    extra = [
        w.warning(
            w.POSSIBLE_OCCLUSION,
            "Tumpukan padat (30 objek); hitungan cenderung lebih rendah dari jumlah sebenarnya.",
        )
    ]
    return _response("crowded", payload, confidences, extra, overlap=0.25, penalty=0.18)


def _low_confidence(payload: ImagePayload) -> InspectResponse:
    confidences = [0.47, 0.45, 0.44, 0.42, 0.41]
    extra = [
        w.warning(
            w.COUNT_UNRELIABLE,
            "Confidence rata-rata rendah; hitungan sebaiknya dikonfirmasi petugas.",
        ),
        w.warning(
            w.LOW_CONFIDENCE_DETECTION,
            "Objek terakhir terdeteksi dengan keyakinan rendah.",
            detection_index=4,
        ),
    ]
    return _response("low_confidence", payload, confidences, extra)


def _empty(payload: ImagePayload) -> InspectResponse:
    extra = [
        w.warning(
            w.NO_OBJECT_DETECTED,
            "Tidak ada kemasan terdeteksi pada foto.",
            Severity.ERROR,
        )
    ]
    return _response("empty", payload, [], extra)


def _low_resolution(payload: ImagePayload) -> InspectResponse:
    confidences = [0.62, 0.58, 0.54]
    extra = [
        w.warning(
            w.IMAGE_LOW_RESOLUTION,
            "Resolusi foto rendah; akurasi deteksi menurun.",
        )
    ]
    return _response("low_resolution", payload, confidences, extra, penalty=0.10)


_BUILDERS = {
    "clean_stack": _clean_stack,
    "partial_occlusion": _partial_occlusion,
    "single_item": _single_item,
    "crowded": _crowded,
    "low_confidence": _low_confidence,
    "empty": _empty,
    "low_resolution": _low_resolution,
}


def pick_scenario(payload: ImagePayload) -> str:
    """Deterministik dari isi berkas: foto yang sama selalu memberi hasil sama."""
    digest = hashlib.sha256(payload.content).digest()
    return SCENARIOS[digest[0] % len(SCENARIOS)]


class MockEngine:
    name = ENGINE_NAME

    def inspect(self, payload: ImagePayload) -> InspectResponse:
        scenario = payload.scenario or pick_scenario(payload)
        return _BUILDERS[scenario](payload)
