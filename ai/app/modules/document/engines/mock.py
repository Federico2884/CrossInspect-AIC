"""Engine mock — 7 skenario deterministik.

Tujuannya bukan mensimulasikan OCR, melainkan mengunci kontrak: setiap skenario
menekan satu sudut kontrak yang harus tetap benar saat engine asli masuk
(multi-halaman, satuan campuran, confidence rendah, field kosong, tipe dokumen
tak dikenal). Tidak ada import torch di jalur ini — image slim harus bisa
melayaninya.
"""

from __future__ import annotations

import hashlib
from datetime import date

from app.modules.document import warnings as w
from app.modules.document.engines.base import DocumentPayload
from app.modules.document.schemas import (
    Confidence,
    DocumentType,
    Item,
    Meta,
    ParseResponse,
    Severity,
    UnitNormalized,
)

ENGINE_NAME = "mock"

SCENARIOS: tuple[str, ...] = (
    "clean_surat_jalan",
    "invoice",
    "multi_page",
    "mixed_units",
    "low_confidence",
    "missing_fields",
    "unknown_type",
)


def _meta(scenario: str) -> Meta:
    # processing_ms diisi service setelah pekerjaan selesai.
    return Meta(engine=ENGINE_NAME, device="cpu", processing_ms=0, scenario=scenario)


def _clean_surat_jalan() -> ParseResponse:
    return ParseResponse(
        document_type=DocumentType.SURAT_JALAN,
        document_number="SJ/2026/08/00142",
        document_date=date(2026, 8, 12),
        sender="PT Sinar Terang Distribusi",
        recipient="Toko Makmur Jaya",
        page_count=1,
        items=[
            Item(
                item_name="Minyak Goreng Sania 2L",
                sku="SNA-2L",
                quantity=20,
                unit_raw="Karton",
                unit_normalized=UnitNormalized.KARTON,
                quantity_per_unit=6,
                source_page=1,
            ),
            Item(
                item_name="Gula Pasir Gulaku 1kg",
                sku="GLK-1K",
                quantity=15,
                unit_raw="Sak",
                unit_normalized=UnitNormalized.SAK,
                source_page=1,
            ),
            Item(
                item_name="Teh Botol Sosro 250ml",
                sku="SSR-250",
                quantity=40,
                unit_raw="Dus",
                unit_normalized=UnitNormalized.BOX,
                quantity_per_unit=24,
                source_page=1,
            ),
        ],
        confidence=Confidence(document_number=0.98, items=[0.96, 0.94, 0.97], overall=0.96),
        meta=_meta("clean_surat_jalan"),
    )


def _invoice() -> ParseResponse:
    return ParseResponse(
        document_type=DocumentType.INVOICE,
        document_number="INV/CIA/2026/0781",
        document_date=date(2026, 8, 9),
        sender="CV Anugerah Pangan",
        recipient="UD Berkah Sentosa",
        page_count=1,
        items=[
            Item(
                item_name="Beras Premium Ramos 5kg",
                sku="BRS-RMS-5",
                quantity=50,
                unit_raw="Sak",
                unit_normalized=UnitNormalized.SAK,
                source_page=1,
            ),
            Item(
                item_name="Tepung Terigu Segitiga Biru 1kg",
                sku="TRG-SGB-1",
                quantity=12,
                unit_raw="Lusin",
                unit_normalized=UnitNormalized.LUSIN,
                quantity_per_unit=12,
                source_page=1,
            ),
        ],
        confidence=Confidence(document_number=0.95, items=[0.93, 0.91], overall=0.93),
        meta=_meta("invoice"),
    )


def _multi_page() -> ParseResponse:
    return ParseResponse(
        document_type=DocumentType.SURAT_JALAN,
        document_number="SJ/2026/08/00155",
        document_date=date(2026, 8, 14),
        sender="PT Nusantara Logistik",
        recipient="Gudang Cabang Bandung",
        page_count=3,
        items=[
            Item(
                item_name="Indomie Goreng",
                sku="IDM-GRG",
                quantity=30,
                unit_raw="Karton",
                unit_normalized=UnitNormalized.KARTON,
                quantity_per_unit=40,
                source_page=1,
            ),
            Item(
                item_name="Kopi Kapal Api 165g",
                sku="KKA-165",
                quantity=18,
                unit_raw="Koli",
                unit_normalized=UnitNormalized.KOLI,
                quantity_per_unit=24,
                source_page=2,
            ),
            Item(
                item_name="Sabun Lifebuoy 85g",
                sku="LFB-85",
                quantity=25,
                unit_raw="Dus",
                unit_normalized=UnitNormalized.BOX,
                quantity_per_unit=48,
                source_page=3,
            ),
        ],
        confidence=Confidence(document_number=0.94, items=[0.92, 0.90, 0.89], overall=0.91),
        meta=_meta("multi_page"),
    )


def _mixed_units() -> ParseResponse:
    return ParseResponse(
        document_type=DocumentType.SURAT_JALAN,
        document_number="SJ/2026/08/00161",
        document_date=date(2026, 8, 15),
        sender="PT Cahaya Abadi",
        recipient="Toko Sumber Rejeki",
        page_count=1,
        items=[
            # 10 karton @ 12 pcs -> cross-check membandingkan 10, total_pieces 120.
            Item(
                item_name="Susu UHT Ultra 250ml",
                sku="ULT-250",
                quantity=10,
                unit_raw="Karton",
                unit_normalized=UnitNormalized.KARTON,
                quantity_per_unit=12,
                source_page=1,
            ),
            Item(
                item_name="Kecap Bango 600ml",
                sku="BNG-600",
                quantity=8,
                unit_raw="Koli",
                unit_normalized=UnitNormalized.KOLI,
                quantity_per_unit=12,
                source_page=1,
            ),
            # Satuan di luar enum: unit_raw dipertahankan, normalized -> unknown.
            Item(
                item_name="Tisu Paseo 250 sheet",
                sku="PSO-250",
                quantity=6,
                unit_raw="Ball",
                unit_normalized=UnitNormalized.UNKNOWN,
                source_page=1,
            ),
            Item(
                item_name="Gula Merah Curah",
                sku=None,
                quantity=25,
                unit_raw="Kg",
                unit_normalized=UnitNormalized.KG,
                source_page=1,
            ),
        ],
        confidence=Confidence(document_number=0.93, items=[0.95, 0.90, 0.72, 0.88], overall=0.86),
        warnings=[
            w.warning(
                w.AMBIGUOUS_UNIT,
                "Satuan 'Ball' tidak ada dalam daftar normalisasi; unit_raw dipertahankan.",
                Severity.WARNING,
                item_index=2,
            ),
        ],
        meta=_meta("mixed_units"),
    )


def _low_confidence() -> ParseResponse:
    return ParseResponse(
        document_type=DocumentType.SURAT_JALAN,
        document_number="SJ/2026/08/0017?",
        document_date=date(2026, 8, 16),
        sender="PT Mitra Boga",
        recipient=None,
        page_count=1,
        items=[
            Item(
                item_name="Saos Sambal ABC 335ml",
                sku=None,
                quantity=12,
                unit_raw="Dus",
                unit_normalized=UnitNormalized.BOX,
                source_page=1,
            ),
            Item(
                item_name="Mie Sedaap Soto",
                sku=None,
                quantity=7,
                unit_raw="Karton",
                unit_normalized=UnitNormalized.KARTON,
                source_page=1,
            ),
        ],
        confidence=Confidence(document_number=0.41, items=[0.38, 0.52], overall=0.44),
        warnings=[
            w.warning(
                w.LOW_CONFIDENCE_ITEM,
                "Kuantitas item tidak terbaca jelas; mohon konfirmasi manual.",
                Severity.WARNING,
                item_index=0,
            ),
            w.warning(
                w.LOW_CONFIDENCE_ITEM,
                "Nama item sebagian tertutup stempel.",
                Severity.WARNING,
                item_index=1,
            ),
            w.warning(w.MISSING_FIELD, "Penerima tidak ditemukan pada dokumen.", Severity.INFO),
        ],
        meta=_meta("low_confidence"),
    )


def _missing_fields() -> ParseResponse:
    return ParseResponse(
        document_type=DocumentType.SURAT_JALAN,
        document_number="SJ-TANPA-TANGGAL-01",
        document_date=None,
        sender=None,
        recipient="Gudang Pusat Surabaya",
        page_count=1,
        items=[
            Item(
                item_name="Air Mineral Aqua 600ml",
                sku="AQA-600",
                quantity=35,
                unit_raw="Dus",
                unit_normalized=UnitNormalized.BOX,
                quantity_per_unit=24,
                source_page=1,
            ),
        ],
        confidence=Confidence(document_number=0.87, items=[0.90], overall=0.72),
        warnings=[
            w.warning(
                w.MISSING_DOCUMENT_DATE,
                "Tanggal dokumen tidak ditemukan; field dikembalikan null.",
                Severity.WARNING,
            ),
            w.warning(w.MISSING_FIELD, "Pengirim tidak ditemukan pada dokumen.", Severity.WARNING),
        ],
        meta=_meta("missing_fields"),
    )


def _unknown_type() -> ParseResponse:
    return ParseResponse(
        document_type=DocumentType.UNKNOWN,
        document_number="",
        document_date=None,
        sender=None,
        recipient=None,
        page_count=1,
        items=[],
        confidence=Confidence(document_number=0.0, items=[], overall=0.11),
        warnings=[
            w.warning(
                w.UNRECOGNISED_DOCUMENT_TYPE,
                "Dokumen tidak dikenali sebagai Surat Jalan maupun Invoice.",
                Severity.ERROR,
            ),
            w.warning(
                w.MISSING_FIELD,
                "Tidak ada baris barang yang berhasil diekstrak.",
                Severity.ERROR,
            ),
        ],
        meta=_meta("unknown_type"),
    )


_BUILDERS = {
    "clean_surat_jalan": _clean_surat_jalan,
    "invoice": _invoice,
    "multi_page": _multi_page,
    "mixed_units": _mixed_units,
    "low_confidence": _low_confidence,
    "missing_fields": _missing_fields,
    "unknown_type": _unknown_type,
}


def resolve_scenario(payload: DocumentPayload) -> str:
    """Skenario eksplisit bila diminta, selain itu dipilih dari hash isi berkas.

    Hash dipakai supaya berkas yang sama selalu menghasilkan response yang sama —
    Laravel bisa menulis test integrasi tanpa perlu tahu skenario apa yang keluar.
    """
    if payload.scenario:
        return payload.scenario
    digest = hashlib.sha256(payload.content).digest()
    return SCENARIOS[digest[0] % len(SCENARIOS)]


class MockEngine:
    name = ENGINE_NAME

    def parse(self, payload: DocumentPayload) -> ParseResponse:
        return _BUILDERS[resolve_scenario(payload)]()
