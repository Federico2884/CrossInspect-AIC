"""Kontrak JSON Modul 2 — Physical Inspection.

Model di file ini adalah penegak (*enforcer*) dari ``CONTRACT.md`` di folder yang
sama, persis seperti hubungan ``document/schemas.py`` dengan kontrak modulnya.

Dua janji yang dijaga di sini:

1. **Bentuk response tidak berubah saat model ditukar.** Bobot YOLO akan dilatih
   ulang; yang berubah hanya ``meta.engine`` / ``meta.model`` dan isi angkanya.
2. **Contract siap multi-kelas sejak awal.** Model hari ini satu kelas, tetapi
   ``class_counts`` sudah per kelas — jadi menambah kelas ``damaged_box`` saat
   training berikutnya tidak memaksa Laravel berubah.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Severity(str, Enum):
    """Sengaja didefinisikan ulang, tidak diimpor dari Modul 1.

    ``main.py`` menetapkan modul tidak saling import. Menyalin enum empat baris
    lebih murah daripada menautkan dua modul yang siklus hidupnya berbeda.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DefectStatus(str, Enum):
    """Status pemeriksaan integritas fisik (parameter ke-3 di dokumen konsep).

    ``UNAVAILABLE`` adalah nilai yang jujur untuk keadaan sekarang: model deteksi
    cacat belum dilatih. Field-nya tetap ada di kontrak supaya Laravel bisa
    menyiapkan UI-nya, dan supaya menghidupkannya nanti bukan perubahan breaking.
    """

    UNAVAILABLE = "unavailable"
    CLEAN = "clean"
    DEFECT_SUSPECTED = "defect_suspected"


class BBox(BaseModel):
    """Kotak pembatas, **ternormalisasi 0.0–1.0** terhadap lebar/tinggi gambar.

    Dinormalisasi, bukan piksel, supaya Laravel bisa menggambar overlay di
    ukuran tampilan berapa pun tanpa menghitung ulang skala — sumber bug klasik
    saat foto 4000px ditampilkan di kanvas 800px.
    """

    model_config = ConfigDict(extra="forbid")

    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_ordering(self) -> BBox:
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("bbox harus memenuhi x1 < x2 dan y1 < y2")
        return self

    @property
    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)


class Detection(BaseModel):
    """Satu objek yang terdeteksi."""

    model_config = ConfigDict(extra="forbid")

    class_name: str = Field(description="Nama kelas apa adanya dari model, tidak dipetakan ulang.")
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BBox


class CountConfidence(BaseModel):
    """Seberapa layak ``detected_count`` dipercaya oleh cross-check engine."""

    model_config = ConfigDict(extra="forbid")

    mean_detection: float = Field(
        ge=0.0, le=1.0, description="Rata-rata confidence seluruh deteksi. 0.0 bila kosong."
    )
    min_detection: float = Field(
        ge=0.0, le=1.0, description="Confidence terendah. Menandai deteksi paling rapuh."
    )
    overall: float = Field(
        ge=0.0,
        le=1.0,
        description="Skor gabungan untuk cross-check. Sudah memperhitungkan indikasi occlusion.",
    )


class DefectFinding(BaseModel):
    """Satu temuan kerusakan. Kosong selama ``DefectStatus.UNAVAILABLE``."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(description="mis. 'penyok', 'robek', 'basah'.")
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BBox | None = None


class DefectReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DefectStatus = DefectStatus.UNAVAILABLE
    findings: list[DefectFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_findings_when_unavailable(self) -> DefectReport:
        # Menjaga agar tidak ada yang diam-diam mengarang temuan cacat sementara
        # modelnya belum ada — ini pembeda antara MVP jujur dan demo palsu.
        if self.status is DefectStatus.UNAVAILABLE and self.findings:
            raise ValueError("findings harus kosong ketika status 'unavailable'")
        if self.status is DefectStatus.DEFECT_SUSPECTED and not self.findings:
            raise ValueError("status 'defect_suspected' menuntut minimal satu finding")
        return self


class InspectWarning(BaseModel):
    """Masalah kualitas inspeksi. Muncul bersama HTTP 200, bukan sebagai error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Severity = Severity.WARNING
    detection_index: int | None = Field(
        default=None, ge=0, description="Menunjuk ke detections[i] bila warning-nya spesifik."
    )


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str = Field(description="'mock' atau id model, mis. 'yolov12n'.")
    device: Literal["cpu"] = "cpu"
    processing_ms: int = Field(ge=0)
    model: str | None = Field(default=None, description="Nama berkas bobot yang dipakai.")
    conf_threshold: float = Field(ge=0.0, le=1.0)
    image_width: int = Field(ge=1)
    image_height: int = Field(ge=1)
    scenario: str | None = None
    debug: dict[str, Any] | None = None


class InspectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_count: int = Field(
        ge=0,
        description=(
            "Jumlah kemasan terluar yang terlihat. Dibandingkan dengan `quantity` "
            "Modul 1 (satuan karton), BUKAN dengan `total_pieces`."
        ),
    )
    class_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Jumlah per nama kelas. Satu entri selama model masih satu kelas.",
    )
    detections: list[Detection] = Field(default_factory=list)
    count_confidence: CountConfidence
    defect: DefectReport = Field(default_factory=DefectReport)
    warnings: list[InspectWarning] = Field(default_factory=list)
    meta: Meta

    @model_validator(mode="after")
    def _check_counts_agree(self) -> InspectResponse:
        # detected_count, class_counts, dan detections adalah tiga tampilan atas
        # fakta yang sama. Kalau ketiganya bisa berbeda, konsumen tidak punya
        # alasan untuk memercayai salah satunya.
        if self.detected_count != len(self.detections):
            raise ValueError(
                f"detected_count ({self.detected_count}) tidak cocok dengan "
                f"jumlah detections ({len(self.detections)})"
            )
        total_by_class = sum(self.class_counts.values())
        if total_by_class != self.detected_count:
            raise ValueError(
                f"total class_counts ({total_by_class}) tidak cocok dengan "
                f"detected_count ({self.detected_count})"
            )
        for index, warning in enumerate(self.warnings):
            if warning.detection_index is not None and warning.detection_index >= len(
                self.detections
            ):
                raise ValueError(
                    f"warnings[{index}].detection_index menunjuk ke deteksi yang tidak ada"
                )
        return self
