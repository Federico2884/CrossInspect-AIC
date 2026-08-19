"""Pembangkit data Surat Jalan sintetis (belum ada rendering di sini).

Memisahkan *data* dari *tampilan* punya alasan praktis: ground truth untuk
evaluasi step 4 lahir dari objek yang sama dengan yang digambar ReportLab,
jadi label evaluasi tidak mungkin melenceng dari isi PDF.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from faker import Faker
from pydantic import BaseModel

from app.modules.document.schemas import DocumentType, Item
from scripts.synthetic import vocab


class GroundTruth(BaseModel):
    """Label evaluasi: hanya field yang benar-benar tercetak di dokumen.

    Sengaja bukan ``ParseResponse`` — confidence dan meta adalah keluaran engine,
    bukan kebenaran dokumen. Tapi ``items`` memakai ``Item`` dari kontrak supaya
    perbandingan saat evaluasi apple-to-apple.
    """

    doc_id: str
    document_type: DocumentType
    document_number: str
    document_date: date | None
    sender: str | None
    recipient: str | None
    page_count: int
    items: list[Item]


@dataclass
class DocumentSpec:
    """Ground truth + petunjuk tampilan untuk satu dokumen."""

    truth: GroundTruth
    layout: str
    title: str
    labels: dict[str, str]
    sender_address: str
    recipient_address: str
    vehicle: str
    driver: str
    footer_note: str
    signatures: tuple[str, str]
    date_format: str
    items_per_page: int = 8
    extras: dict[str, str] = field(default_factory=dict)


LAYOUTS = ("classic", "boxed", "minimal")
DATE_FORMATS = ("iso", "slash", "long")


def _company(rng: random.Random) -> str:
    return f"{rng.choice(vocab.COMPANY_PREFIXES)} {rng.choice(vocab.COMPANY_WORDS)}"


def _document_number(rng: random.Random, when: date) -> str:
    serial = rng.randint(1, 9999)
    roman = vocab.ROMAN_MONTHS[when.month - 1]
    return rng.choice(
        (
            f"SJ/{when.year}/{when.month:02d}/{serial:05d}",
            f"SJ-{when.month:02d}{when.day:02d}-{serial:03d}",
            f"{serial:04d}/SJ/{roman}/{when.year}",
            f"SJ.{when.year % 100:02d}.{serial:04d}",
            f"DO/{rng.randint(100, 999)}/{when.year}",
        )
    )


def _items(rng: random.Random, count: int, page_count: int, items_per_page: int) -> list[Item]:
    chosen = rng.sample(vocab.PRODUCTS, k=min(count, len(vocab.PRODUCTS)))
    units = list(vocab.UNIT_MAP)
    items: list[Item] = []

    for index, (name, sku_prefix) in enumerate(chosen):
        unit_raw = rng.choice(units)
        quantity_per_unit = None
        if unit_raw in vocab.UNITS_WITH_CONTENTS and rng.random() < 0.7:
            quantity_per_unit = rng.choice((6, 10, 12, 20, 24, 40, 48))

        items.append(
            Item(
                item_name=name,
                sku=f"{sku_prefix}-{rng.randint(100, 999)}" if rng.random() < 0.75 else None,
                quantity=rng.randint(1, 120),
                unit_raw=unit_raw,
                unit_normalized=vocab.UNIT_MAP[unit_raw],
                quantity_per_unit=quantity_per_unit,
                source_page=min(index // items_per_page + 1, page_count),
            )
        )
    return items


def build_spec(seed: int, doc_id: str) -> DocumentSpec:
    """Bangun satu dokumen secara deterministik dari ``seed``.

    Seed yang sama selalu menghasilkan dokumen yang sama, sehingga satu berkas
    bisa diregenerasi tanpa membuat ulang seluruh dataset.
    """
    rng = random.Random(seed)
    faker = Faker("id_ID")
    faker.seed_instance(seed)

    when = date(2026, 1, 1) + timedelta(days=rng.randint(0, 240))
    items_per_page = rng.choice((6, 8, 10))
    item_count = rng.randint(1, 14)
    page_count = max(1, (item_count - 1) // items_per_page + 1)

    truth = GroundTruth(
        doc_id=doc_id,
        document_type=DocumentType.SURAT_JALAN,
        document_number=_document_number(rng, when),
        document_date=when,
        sender=_company(rng),
        recipient=_company(rng),
        page_count=page_count,
        items=_items(rng, item_count, page_count, items_per_page),
    )

    return DocumentSpec(
        truth=truth,
        layout=rng.choice(LAYOUTS),
        title=rng.choice(vocab.TITLES),
        labels={
            "number": rng.choice(vocab.LABEL_NUMBER),
            "date": rng.choice(vocab.LABEL_DATE),
            "sender": rng.choice(vocab.LABEL_SENDER),
            "recipient": rng.choice(vocab.LABEL_RECIPIENT),
            "item": rng.choice(vocab.LABEL_ITEM),
            "qty": rng.choice(vocab.LABEL_QTY),
            "unit": rng.choice(vocab.LABEL_UNIT),
            "sku": rng.choice(vocab.LABEL_SKU),
        },
        sender_address=faker.address().replace("\n", ", "),
        recipient_address=faker.address().replace("\n", ", "),
        vehicle=f"{rng.choice(('B', 'D', 'L', 'N', 'AB'))} {rng.randint(1000, 9999)} "
        f"{rng.choice(('ABC', 'XYZ', 'KLM', 'PQR'))}",
        driver=faker.name(),
        footer_note=rng.choice(vocab.FOOTER_NOTES),
        signatures=rng.choice(vocab.SIGNATURE_LABELS),
        date_format=rng.choice(DATE_FORMATS),
        items_per_page=items_per_page,
    )


def format_date(when: date, style: str) -> str:
    if style == "iso":
        return when.strftime("%d-%m-%Y")
    if style == "slash":
        return when.strftime("%d/%m/%Y")
    return f"{when.day} {vocab.MONTHS_ID[when.month - 1]} {when.year}"
