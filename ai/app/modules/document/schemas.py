"""Kontrak JSON Modul 1 — Document Parsing.

Model di file ini adalah penegak (*enforcer*) dari ``CONTRACT.md``. Bentuk
response tidak boleh berubah saat engine mock diganti model asli di step 4;
yang berubah hanya ``meta.engine``.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentType(str, Enum):
    SURAT_JALAN = "SURAT_JALAN"
    INVOICE = "INVOICE"
    UNKNOWN = "UNKNOWN"


class UnitNormalized(str, Enum):
    """Satuan yang dikenali cross-check engine.

    ``unit_raw`` tetap menyimpan tulisan asli dokumen (``dus``, ``zak``,
    ``ball``, ``slop``, ...) supaya tidak ada data yang hilang saat satuan di
    luar daftar ini muncul — enum tertutup di sini hanya untuk sisi konsumen.
    """

    PCS = "pcs"
    BOX = "box"
    KARTON = "karton"
    KOLI = "koli"
    KG = "kg"
    LUSIN = "lusin"
    ROLL = "roll"
    SAK = "sak"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Item(BaseModel):
    """Satu baris barang pada dokumen."""

    model_config = ConfigDict(extra="forbid")

    item_name: str
    sku: str | None = None
    quantity: int = Field(ge=0, description="Jumlah dalam satuan unit_raw, bukan dalam pcs.")
    unit_raw: str = Field(description="Satuan persis seperti tertulis di dokumen.")
    unit_normalized: UnitNormalized = UnitNormalized.UNKNOWN
    quantity_per_unit: int | None = Field(
        default=None, ge=1, description="Isi per satuan, mis. 12 untuk '10 karton @ 12 pcs'."
    )
    total_pieces: int | None = Field(
        default=None, ge=0, description="quantity * quantity_per_unit, bila diketahui."
    )
    source_page: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _derive_total_pieces(self) -> Item:
        # Aritmetika dibuat eksplisit supaya cross-check engine tidak menebak:
        # untuk '10 karton @ 12 pcs', Modul 2 menghitung 10 kardus, bukan 120.
        if self.total_pieces is None and self.quantity_per_unit is not None:
            self.total_pieces = self.quantity * self.quantity_per_unit
        return self


class Confidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_number: float = Field(ge=0.0, le=1.0)
    items: list[float] = Field(default_factory=list)
    overall: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_item_scores(self) -> Confidence:
        for score in self.items:
            if not 0.0 <= score <= 1.0:
                raise ValueError("confidence.items entries must be within [0.0, 1.0]")
        return self


class ParseWarning(BaseModel):
    """Masalah kualitas parsing. Muncul bersama HTTP 200, bukan sebagai error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Severity = Severity.WARNING
    item_index: int | None = Field(default=None, ge=0)


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str = Field(description="'mock' sekarang; id model saat engine asli dipakai.")
    device: Literal["cpu"] = "cpu"
    processing_ms: int = Field(ge=0)
    scenario: str | None = None
    debug: dict[str, Any] | None = None


class ParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    document_number: str
    document_date: date | None = None
    sender: str | None = None
    recipient: str | None = None
    page_count: int = Field(default=1, ge=1)
    items: list[Item] = Field(default_factory=list)
    confidence: Confidence
    warnings: list[ParseWarning] = Field(default_factory=list)
    meta: Meta

    @model_validator(mode="after")
    def _check_source_pages(self) -> ParseResponse:
        for index, item in enumerate(self.items):
            if item.source_page > self.page_count:
                raise ValueError(
                    f"items[{index}].source_page ({item.source_page}) exceeds "
                    f"page_count ({self.page_count})"
                )
        return self
