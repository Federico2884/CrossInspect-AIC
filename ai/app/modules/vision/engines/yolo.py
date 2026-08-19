"""Engine YOLO — deteksi kemasan sungguhan.

``ultralytics`` dan ``torch`` di-import **di dalam fungsi**, bukan di level modul.
Alasannya: image slim tidak memasang keduanya, dan service harus tetap bisa
menyala di sana (jatuh ke mock) alih-alih gagal saat startup.

Nama kelas dibaca dari bobot saat runtime, tidak di-hardcode — jadi model hasil
training ulang dengan kelas berbeda langsung terpakai tanpa mengubah kode.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from typing import Any

from app.core.config import get_settings
from app.modules.vision import warnings as w
from app.modules.vision.engines.base import ImagePayload
from app.modules.vision.schemas import (
    BBox,
    CountConfidence,
    DefectReport,
    DefectStatus,
    Detection,
    InspectResponse,
    InspectWarning,
    Meta,
    Severity,
)


def is_available() -> bool:
    """True bila stack ML terpasang dan berkas bobot benar-benar ada."""
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        return False
    return get_settings().vision_model_file.is_file()


@lru_cache(maxsize=1)
def _load_model() -> Any:
    """Bobot dimuat sekali lalu dipakai ulang.

    Tanpa cache, tiap request membayar ulang biaya load (~detik di CPU) dan
    endpoint akan terasa jauh lebih lambat daripada inferensinya sendiri.
    """
    from ultralytics import YOLO

    settings = get_settings()
    return YOLO(str(settings.vision_model_file))


def preload() -> None:
    """Muat bobot **dan** jalankan satu inferensi tiruan.

    Memuat bobot saja belum cukup: ultralytics masih menunda sebagian inisialisasi
    sampai prediksi pertama. Diukur di CPU — hanya load: request pertama ~1,2 detik;
    load + inferensi tiruan: ~0,12 detik, sama dengan request berikutnya.
    """
    from PIL import Image

    settings = get_settings()
    model = _load_model()
    blank = Image.new("RGB", (settings.vision_imgsz, settings.vision_imgsz), (128, 128, 128))
    model.predict(source=blank, conf=settings.vision_conf_threshold, verbose=False)


def _iou(a: BBox, b: BBox) -> float:
    inter_x1, inter_y1 = max(a.x1, b.x1), max(a.y1, b.y1)
    inter_x2, inter_y2 = min(a.x2, b.x2), min(a.y2, b.y2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    union = a.area + b.area - intersection
    return intersection / union if union > 0 else 0.0


def _occlusion_ratio(detections: list[Detection]) -> float:
    """Porsi deteksi yang bertindihan cukup berarti dengan deteksi lain.

    Ini proksi untuk risiko *undercount*: kalau kotak-kotak saling menutupi di
    bidang gambar, kemungkinan besar ada kemasan di belakang yang tidak terlihat
    kamera sama sekali. Bukan pengukuran occlusion yang sesungguhnya — hanya
    sinyal yang cukup untuk menaikkan bendera.
    """
    if len(detections) < 2:
        return 0.0
    settings = get_settings()
    overlapping = 0
    for index, current in enumerate(detections):
        others = detections[:index] + detections[index + 1 :]
        if any(_iou(current.bbox, other.bbox) > settings.vision_occlusion_iou for other in others):
            overlapping += 1
    return overlapping / len(detections)


def _build_warnings(
    detections: list[Detection],
    payload: ImagePayload,
    occlusion_ratio: float,
    mean_confidence: float,
) -> list[InspectWarning]:
    settings = get_settings()
    result: list[InspectWarning] = [w.defect_unavailable()]

    if not detections:
        result.append(
            w.warning(
                w.NO_OBJECT_DETECTED,
                "Tidak ada kemasan terdeteksi pada foto.",
                Severity.ERROR,
            )
        )
        return result

    if min(payload.width, payload.height) < settings.vision_min_resolution:
        result.append(
            w.warning(
                w.IMAGE_LOW_RESOLUTION,
                f"Sisi terpendek foto {min(payload.width, payload.height)} px, "
                f"di bawah {settings.vision_min_resolution} px; akurasi deteksi menurun.",
            )
        )

    if occlusion_ratio >= settings.vision_occlusion_ratio_alert:
        result.append(
            w.warning(
                w.POSSIBLE_OCCLUSION,
                f"{round(occlusion_ratio * 100)}% kotak saling bertindihan; sebagian kemasan "
                "kemungkinan tertutup dan tidak ikut terhitung.",
            )
        )

    if mean_confidence < settings.vision_unreliable_below:
        result.append(
            w.warning(
                w.COUNT_UNRELIABLE,
                "Confidence rata-rata rendah; hitungan sebaiknya dikonfirmasi petugas.",
            )
        )

    margin = settings.vision_conf_threshold + settings.vision_low_confidence_margin
    for index, detection in enumerate(detections):
        if detection.confidence < margin:
            result.append(
                w.warning(
                    w.LOW_CONFIDENCE_DETECTION,
                    f"Objek ke-{index + 1} terdeteksi dengan keyakinan rendah "
                    f"({detection.confidence:.2f}).",
                    detection_index=index,
                )
            )
    return result


def _to_detections(result: Any, width: int, height: int, names: dict[int, str]) -> list[Detection]:
    """Ubah keluaran ultralytics menjadi objek kontrak kita.

    Koordinat ultralytics dalam piksel; kontrak memakai 0.0–1.0, jadi dibagi
    dimensi gambar di sini — satu-satunya tempat konversi itu terjadi.
    """
    detections: list[Detection] = []
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return detections

    for box in boxes:
        x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
        class_id = int(box.cls[0])
        detections.append(
            Detection(
                class_name=names.get(class_id, str(class_id)),
                confidence=round(float(box.conf[0]), 4),
                bbox=BBox(
                    x1=max(0.0, min(1.0, x1 / width)),
                    y1=max(0.0, min(1.0, y1 / height)),
                    x2=max(0.0, min(1.0, x2 / width)),
                    y2=max(0.0, min(1.0, y2 / height)),
                ),
            )
        )
    return detections


class YoloEngine:
    """Deteksi kuantitas. Integritas fisik belum dicakup model ini."""

    name = "yolo"

    def inspect(self, payload: ImagePayload) -> InspectResponse:
        from PIL import Image

        settings = get_settings()
        model = _load_model()

        image = Image.open(BytesIO(payload.content)).convert("RGB")
        results = model.predict(
            source=image,
            conf=settings.vision_conf_threshold,
            imgsz=settings.vision_imgsz,
            verbose=False,
        )

        names: dict[int, str] = dict(getattr(model, "names", {}) or {})
        detections = _to_detections(results[0], payload.width, payload.height, names)

        # Kotak yang gagal validasi geometri (mis. lebar nol setelah pembulatan)
        # sudah tersaring oleh Pydantic saat konstruksi di _to_detections.
        confidences = [detection.confidence for detection in detections]
        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        occlusion_ratio = _occlusion_ratio(detections)

        class_counts: dict[str, int] = {}
        for detection in detections:
            class_counts[detection.class_name] = class_counts.get(detection.class_name, 0) + 1

        return InspectResponse(
            detected_count=len(detections),
            class_counts=class_counts,
            detections=detections,
            count_confidence=CountConfidence(
                mean_detection=round(mean_confidence, 4),
                min_detection=round(min(confidences), 4) if confidences else 0.0,
                # Occlusion menurunkan kelayakan percaya pada hitungan, bukan
                # pada tiap deteksi — itulah kenapa penaltinya hanya di sini.
                overall=round(max(0.0, mean_confidence * (1.0 - occlusion_ratio * 0.5)), 4),
            ),
            defect=DefectReport(status=DefectStatus.UNAVAILABLE),
            warnings=_build_warnings(detections, payload, occlusion_ratio, mean_confidence),
            meta=Meta(
                engine=self.name,
                device="cpu",
                processing_ms=0,
                model=settings.vision_model_file.name,
                conf_threshold=settings.vision_conf_threshold,
                image_width=payload.width,
                image_height=payload.height,
                scenario=None,
                debug={"occlusion_ratio": round(occlusion_ratio, 4), "classes": names},
            ),
        )
