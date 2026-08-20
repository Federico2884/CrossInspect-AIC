"""Kontrak JSON Modul 3 — Cross-Check Engine.

Model di file ini adalah penegak (*enforcer*) dari ``CONTRACT.md`` di folder yang
sama.

Berbeda dari dua modul lain, modul ini **sengaja mengimpor** schema mereka.
``main.py`` menyebut modul tidak saling import, dan itu benar untuk Modul 1 dan 2
yang memang sederajat. Modul 3 adalah konsumen keduanya — mendefinisikan ulang
bentuk masukannya di sini justru menciptakan sumber kebenaran kedua yang akan
melenceng diam-diam. Dengan mengimpor, perubahan kontrak hulu meledak di sini
sebagai error validasi, bukan sebagai selisih angka yang salah beberapa minggu
kemudian.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.document.schemas import ParseResponse, UnitNormalized
from app.modules.vision.schemas import InspectResponse


class Severity(str, Enum):
    # Sama dengan milik Modul 1 dan 2. Kontrak induk menyebutnya berlaku
    # service-wide, jadi enum ini kandidat untuk diangkat ke ``app/core/``
    # begitu ketiga modul bisa disentuh dalam satu perubahan.
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CrossCheckStatus(str, Enum):
    """Vonis akhir.

    ``PARTIAL`` sengaja dipisahkan dari ``MATCH``: menyebut "cocok" padahal
    sebagian kiriman tidak pernah diperiksa adalah jaminan palsu.
    """

    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    MISMATCH = "MISMATCH"
    UNVERIFIABLE = "UNVERIFIABLE"


class ExclusionReason(str, Enum):
    """Kenapa sebuah baris tidak ikut dijumlahkan."""

    UNIT_IS_WEIGHT = "UNIT_IS_WEIGHT"
    UNIT_NOT_CARDBOARD = "UNIT_NOT_CARDBOARD"
    UNIT_UNKNOWN = "UNIT_UNKNOWN"


class ParameterStatus(str, Enum):
    """Status parameter yang belum terjawab model saat ini.

    Hanya ``unavailable`` yang dipakai hari ini; dua nilai lain sudah ada supaya
    model multi-kelas dan model kerusakan nanti tidak mengubah bentuk respons.
    """

    UNAVAILABLE = "unavailable"
    VERIFIED = "verified"
    MISMATCH = "mismatch"


class _ItemRef(BaseModel):
    """Rujukan ke satu baris barang di dokumen."""

    model_config = ConfigDict(extra="forbid")

    item_index: int = Field(ge=0, description="Posisi baris di items[] milik Modul 1.")
    item_name: str
    quantity: int = Field(ge=0, description="Dalam satuan unit_raw, bukan pieces.")
    unit_raw: str
    unit_normalized: UnitNormalized


class CountedItem(_ItemRef):
    """Baris yang ikut dijumlahkan ke ``document_total``."""


class ExcludedItem(_ItemRef):
    """Baris yang dikecualikan, beserta alasannya."""

    reason: ExclusionReason


class QuantityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_total: int = Field(
        ge=0, description="Jumlah quantity dari baris berkardus saja, bukan seluruh dokumen."
    )
    detected_total: int = Field(ge=0, description="detected_count dari Modul 2, apa adanya.")
    difference: int = Field(description="detected_total - document_total.")
    counted_items: list[CountedItem] = Field(default_factory=list)
    excluded_items: list[ExcludedItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _arithmetic_holds(self) -> QuantityReport:
        # Selisih tidak boleh dihitung ulang oleh klien dengan hasil berbeda.
        expected = self.detected_total - self.document_total
        if self.difference != expected:
            raise ValueError(f"difference harus {expected}, bukan {self.difference}")
        return self


class ParameterReport(BaseModel):
    """Parameter verifikasi yang belum bisa dijawab."""

    model_config = ConfigDict(extra="forbid")

    status: ParameterStatus = ParameterStatus.UNAVAILABLE
    reason: str | None = None

    @model_validator(mode="after")
    def _unavailable_needs_a_reason(self) -> ParameterReport:
        # "Belum diperiksa" tanpa penjelasan tidak berguna bagi petugas gudang —
        # dia perlu tahu apakah ini kegagalan atau memang di luar kemampuan alat.
        if self.status is ParameterStatus.UNAVAILABLE and not self.reason:
            raise ValueError("status 'unavailable' menuntut reason yang menjelaskan")
        return self


class CrossCheckWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Severity = Severity.WARNING
    item_index: int | None = Field(
        default=None, ge=0, description="Baris yang dimaksud, bila warning-nya spesifik."
    )


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str = Field(default="rules", description="Selalu 'rules' — tidak ada model di sini.")
    device: Literal["cpu"] = "cpu"
    processing_ms: int = Field(ge=0)
    document_engine: str = Field(description="meta.engine dari respons Modul 1 yang dipakai.")
    vision_engine: str = Field(description="meta.engine dari respons Modul 2 yang dipakai.")
    scenario: str | None = None
    debug: dict[str, Any] | None = None


class CrossCheckRequest(BaseModel):
    """Dua respons hulu, apa adanya."""

    model_config = ConfigDict(extra="forbid")

    document: ParseResponse
    vision: InspectResponse


class CrossCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CrossCheckStatus
    quantity: QuantityReport
    identity: ParameterReport
    integrity: ParameterReport
    warnings: list[CrossCheckWarning] = Field(default_factory=list)
    meta: Meta

    @model_validator(mode="after")
    def _match_means_fully_checked(self) -> CrossCheckResponse:
        # Inti kontrak ini: MATCH hanya boleh keluar kalau tidak ada satu pun
        # baris yang lolos dari pemeriksaan. Kalau ada, vonisnya PARTIAL.
        if self.status is CrossCheckStatus.MATCH and self.excluded_count:
            raise ValueError(
                "MATCH tidak boleh dipakai saat ada baris dikecualikan — gunakan PARTIAL"
            )
        if self.status is CrossCheckStatus.MATCH and self.quantity.difference != 0:
            raise ValueError("MATCH menuntut difference == 0")
        return self

    @property
    def excluded_count(self) -> int:
        return len(self.quantity.excluded_items)
