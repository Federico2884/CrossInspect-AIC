"""Rekonsiliasi Modul 1 vs Modul 2.

Murni aturan: tidak ada model, tidak ada I/O, tidak ada torch. Seluruh modul ini
bisa diuji tanpa menyalakan apa pun — dan itu disengaja, karena logika inilah yang
paling mudah salah tanpa ketahuan.
"""

from __future__ import annotations

import time

from app.modules.crosscheck import warnings as w
from app.modules.crosscheck.schemas import (
    CountedItem,
    CrossCheckRequest,
    CrossCheckResponse,
    CrossCheckStatus,
    CrossCheckWarning,
    ExcludedItem,
    ExclusionReason,
    Meta,
    ParameterReport,
    ParameterStatus,
    QuantityReport,
)
from app.modules.document.schemas import DocumentType, ParseResponse, UnitNormalized
from app.modules.document.warnings import LOW_CONFIDENCE_ITEM
from app.modules.vision.schemas import DefectStatus, InspectResponse
from app.modules.vision.warnings import COUNT_UNRELIABLE, NO_OBJECT_DETECTED, POSSIBLE_OCCLUSION

# Satuan yang berarti "satu kemasan kardus" — satu-satunya yang sebanding dengan
# kelas `cardboard` milik Modul 2. Menambah satuan ke sini tanpa melatih model
# mengenalinya akan melahirkan selisih palsu, jadi daftar ini bergerak bersama
# bobot, bukan mendahuluinya.
CARDBOARD_UNITS: frozenset[UnitNormalized] = frozenset(
    {UnitNormalized.KARTON, UnitNormalized.BOX, UnitNormalized.KOLI}
)


def classify_unit(unit: UnitNormalized) -> ExclusionReason | None:
    """``None`` berarti baris ini ikut dihitung."""
    if unit in CARDBOARD_UNITS:
        return None
    if unit is UnitNormalized.KG:
        return ExclusionReason.UNIT_IS_WEIGHT
    if unit is UnitNormalized.UNKNOWN:
        return ExclusionReason.UNIT_UNKNOWN
    # pcs, lusin, roll, sak — benda fisik, tetapi bukan kardus.
    return ExclusionReason.UNIT_NOT_CARDBOARD


def _split_items(document: ParseResponse) -> tuple[list[CountedItem], list[ExcludedItem]]:
    counted: list[CountedItem] = []
    excluded: list[ExcludedItem] = []

    for index, item in enumerate(document.items):
        common = {
            "item_index": index,
            "item_name": item.item_name,
            # quantity, bukan total_pieces: kamera hanya melihat kemasan terluar.
            "quantity": item.quantity,
            "unit_raw": item.unit_raw,
            "unit_normalized": item.unit_normalized,
        }
        reason = classify_unit(item.unit_normalized)
        if reason is None:
            counted.append(CountedItem(**common))
        else:
            excluded.append(ExcludedItem(**common, reason=reason))

    return counted, excluded


def _low_confidence_indices(document: ParseResponse) -> set[int]:
    """Baris yang Modul 1 sendiri tandai lemah.

    Sengaja memakai penilaian Modul 1, bukan ambang baru di sini — dua ambang
    untuk hal yang sama pasti akan berbeda cepat atau lambat.
    """
    return {
        warning.item_index
        for warning in document.warnings
        if warning.code == LOW_CONFIDENCE_ITEM and warning.item_index is not None
    }


def _has(response: InspectResponse, code: str) -> bool:
    return any(warning.code == code for warning in response.warnings)


def _integrity_of(vision: InspectResponse) -> ParameterReport:
    if vision.defect.status is DefectStatus.UNAVAILABLE:
        return ParameterReport(
            status=ParameterStatus.UNAVAILABLE,
            reason="Model deteksi kerusakan belum tersedia, jadi kemasan belum diperiksa.",
        )
    if vision.defect.status is DefectStatus.CLEAN:
        return ParameterReport(status=ParameterStatus.VERIFIED)
    return ParameterReport(status=ParameterStatus.MISMATCH)


def _identity_report() -> ParameterReport:
    # Tetap `unavailable` sampai ada model yang benar-benar mencocokkan nama
    # barang. Menambah kelas ke model saja belum cukup: memetakan "cardboard_susu"
    # ke "Susu UHT Ultra 250ml" adalah persoalan tersendiri.
    return ParameterReport(
        status=ParameterStatus.UNAVAILABLE,
        reason="Model vision hanya mengenali satu kelas, sehingga varian produk "
        "tidak dapat dicocokkan dengan baris dokumen.",
    )


def _decide(
    *,
    counted: list[CountedItem],
    excluded: list[ExcludedItem],
    difference: int,
    count_unreliable: bool,
) -> CrossCheckStatus:
    """Urutan vonis, sesuai CONTRACT.md. Yang pertama cocok menang."""
    if count_unreliable:
        return CrossCheckStatus.UNVERIFIABLE
    if not counted:
        return CrossCheckStatus.UNVERIFIABLE
    if difference != 0:
        return CrossCheckStatus.MISMATCH
    if excluded:
        return CrossCheckStatus.PARTIAL
    return CrossCheckStatus.MATCH


def cross_check(request: CrossCheckRequest) -> CrossCheckResponse:
    started = time.perf_counter()
    document, vision = request.document, request.vision

    counted, excluded = _split_items(document)
    document_total = sum(item.quantity for item in counted)
    detected_total = vision.detected_count
    difference = detected_total - document_total

    count_unreliable = _has(vision, COUNT_UNRELIABLE)
    status = _decide(
        counted=counted,
        excluded=excluded,
        difference=difference,
        count_unreliable=count_unreliable,
    )

    notes: list[CrossCheckWarning] = [w.identity_not_verified()]
    integrity = _integrity_of(vision)
    if integrity.status is ParameterStatus.UNAVAILABLE:
        notes.append(w.integrity_not_verified())

    if count_unreliable:
        notes.append(w.count_unreliable_upstream())
    if _has(vision, NO_OBJECT_DETECTED):
        notes.append(w.no_object_detected_upstream())
    if not counted:
        notes.append(w.no_countable_items())

    # Occlusion hanya menjelaskan selisih yang kurang, bukan yang lebih: kotak
    # terhalang membuat hitungan lebih rendah, tidak pernah lebih tinggi.
    if status is CrossCheckStatus.MISMATCH and difference < 0 and _has(vision, POSSIBLE_OCCLUSION):
        notes.append(w.count_possibly_understated(-difference))

    weak = _low_confidence_indices(document)
    notes.extend(
        w.document_low_confidence(item.item_index, item.item_name)
        for item in counted
        if item.item_index in weak
    )

    notes.extend(
        w.partial_coverage(item.item_index, item.item_name, item.unit_raw) for item in excluded
    )

    if document.document_type is DocumentType.UNKNOWN:
        notes.append(w.document_type_unknown())

    return CrossCheckResponse(
        status=status,
        quantity=QuantityReport(
            document_total=document_total,
            detected_total=detected_total,
            difference=difference,
            counted_items=counted,
            excluded_items=excluded,
        ),
        identity=_identity_report(),
        integrity=integrity,
        warnings=notes,
        meta=Meta(
            processing_ms=int((time.perf_counter() - started) * 1000),
            document_engine=document.meta.engine,
            vision_engine=vision.meta.engine,
        ),
    )
