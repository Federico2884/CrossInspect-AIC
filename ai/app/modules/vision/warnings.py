"""Katalog kode warning Modul 2.

Konstanta, bukan string literal, supaya engine mock dan YOLO memancarkan kode
yang identik — Laravel mencocokkan berdasarkan ``code``, sedangkan ``message``
bebas berubah kalimatnya.
"""

from app.modules.vision.schemas import InspectWarning, Severity

NO_OBJECT_DETECTED = "NO_OBJECT_DETECTED"
LOW_CONFIDENCE_DETECTION = "LOW_CONFIDENCE_DETECTION"
COUNT_UNRELIABLE = "COUNT_UNRELIABLE"
POSSIBLE_OCCLUSION = "POSSIBLE_OCCLUSION"
DEFECT_CHECK_UNAVAILABLE = "DEFECT_CHECK_UNAVAILABLE"
IMAGE_LOW_RESOLUTION = "IMAGE_LOW_RESOLUTION"


def warning(
    code: str,
    message: str,
    severity: Severity = Severity.WARNING,
    detection_index: int | None = None,
) -> InspectWarning:
    return InspectWarning(
        code=code, message=message, severity=severity, detection_index=detection_index
    )


def defect_unavailable() -> InspectWarning:
    """Selalu disertakan selama model deteksi cacat belum ada.

    Diucapkan sebagai warning, bukan didiamkan, supaya UI tidak menampilkan
    "kemasan aman" untuk pemeriksaan yang sebenarnya tidak pernah dijalankan.
    """
    return warning(
        DEFECT_CHECK_UNAVAILABLE,
        "Pemeriksaan integritas fisik belum tersedia; hanya kuantitas yang diverifikasi.",
        Severity.INFO,
    )
