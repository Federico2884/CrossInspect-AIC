"""Fixture bersama untuk test Modul 3.

Modul ini tidak menyentuh berkas maupun model, jadi tidak ada gambar atau PDF
yang perlu dibuat. Yang dibutuhkan hanya dua respons hulu yang **valid menurut
schema aslinya** — dibangun lewat model Pydantic milik Modul 1 dan 2, bukan lewat
dict mentah. Kalau kontrak hulu berubah, builder di sini ikut gagal, dan itulah
gunanya.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.document import schemas as doc
from app.modules.vision import schemas as vis


def item(
    name: str = "Susu UHT Ultra 250ml",
    quantity: int = 10,
    unit_raw: str = "Karton",
    unit: doc.UnitNormalized = doc.UnitNormalized.KARTON,
    quantity_per_unit: int | None = 12,
) -> doc.Item:
    return doc.Item(
        item_name=name,
        quantity=quantity,
        unit_raw=unit_raw,
        unit_normalized=unit,
        quantity_per_unit=quantity_per_unit,
        total_pieces=quantity * quantity_per_unit if quantity_per_unit else None,
        source_page=1,
    )


def make_document(
    items: list[doc.Item] | None = None,
    warnings: list[doc.ParseWarning] | None = None,
    document_type: doc.DocumentType = doc.DocumentType.SURAT_JALAN,
    engine: str = "mock",
) -> doc.ParseResponse:
    items = [item()] if items is None else items
    return doc.ParseResponse(
        document_type=document_type,
        document_number="SJ/2026/08/00161",
        page_count=1,
        items=items,
        confidence=doc.Confidence(
            document_number=0.93,
            items=[0.95] * len(items),  # harus sejajar dengan items
            overall=0.9,
        ),
        warnings=warnings or [],
        meta=doc.Meta(engine=engine, processing_ms=3),
    )


def make_vision(
    detected_count: int = 10,
    warnings: list[vis.InspectWarning] | None = None,
    defect_status: vis.DefectStatus = vis.DefectStatus.UNAVAILABLE,
    engine: str = "mock",
) -> vis.InspectResponse:
    detections = [
        vis.Detection(
            class_name="cardboard",
            confidence=0.86,
            bbox=vis.BBox(x1=0.1, y1=0.1, x2=0.2, y2=0.2),
        )
        for _ in range(detected_count)
    ]
    return vis.InspectResponse(
        detected_count=detected_count,
        class_counts={"cardboard": detected_count} if detected_count else {},
        detections=detections,
        count_confidence=vis.CountConfidence(
            mean_detection=0.86, min_detection=0.7, overall=0.86
        ),
        defect=vis.DefectReport(status=defect_status),
        warnings=warnings or [],
        meta=vis.Meta(
            engine=engine,
            processing_ms=12,
            model="inspection.pt",
            conf_threshold=0.4,
            image_width=1280,
            image_height=960,
        ),
    )


def doc_warning(code: str, item_index: int | None = None) -> doc.ParseWarning:
    return doc.ParseWarning(
        code=code, message="…", severity=doc.Severity.WARNING, item_index=item_index
    )


def vis_warning(code: str) -> vis.InspectWarning:
    return vis.InspectWarning(code=code, message="…", severity=vis.Severity.WARNING)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
