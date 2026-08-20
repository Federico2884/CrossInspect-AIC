"""Menghitung skor satu dokumen dan meringkasnya jadi angka agregat.

Prinsip yang dipegang: **jangan pernah melaporkan satu angka akurasi**.

Pengukuran kasar di step 4 menemukan halaman yang namanya benar 8 dari 10 tapi
jumlahnya hanya 2 dari 10. Satu angka gabungan akan menyembunyikan persis hal
itu, padahal jumlah yang salah jauh lebih berbahaya daripada nama yang salah
ketik: nama aneh langsung terlihat manusia, sedangkan jumlah yang salah diam-
diam merusak hasil cross-check.

Karena itu "menemukan baris" dan "membaca isi baris" dihitung terpisah, dan
tiap field punya angkanya sendiri.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from scripts.evaluation.matching import (
    DEFAULT_THRESHOLD,
    MatchResult,
    match_items,
    similarity,
)

# Ambang untuk menganggap nama pengirim/penerima "benar" walau ejaannya beda
# tipis. Field ini prosa bebas, bukan kode, jadi ejaan persis terlalu kejam.
PARTY_THRESHOLD = 0.90


@dataclass
class DocumentScore:
    """Hasil satu panggilan engine: satu PDF, atau satu halaman foto."""

    doc_id: str
    source: str  # "pdf" atau "image"
    page: int | None  # nomor halaman untuk sumber foto; None untuk PDF utuh
    severity: str | None
    layout: str | None
    engine: str
    latency_s: float
    parsed: bool  # model mengembalikan sesuatu yang bisa dibaca

    # Field tingkat dokumen. None = tidak dinilai (mis. halaman 2 foto).
    document_type_ok: bool | None = None
    document_number_ok: bool | None = None
    document_date_ok: bool | None = None
    sender_ok: bool | None = None
    recipient_ok: bool | None = None
    page_count_ok: bool | None = None

    # Menemukan baris.
    rows_truth: int = 0
    rows_predicted: int = 0
    rows_matched: int = 0
    rows_exact_name: int = 0

    # Membaca isi baris — penyebut selalu rows_matched.
    quantity_ok: int = 0
    unit_raw_ok: int = 0
    unit_normalized_ok: int = 0
    quantity_per_unit_ok: int = 0
    sku_ok: int = 0
    source_page_ok: int = 0

    # (confidence, benar?) per baris terjodoh, untuk mengecek kalibrasi.
    confidence_pairs: list[tuple[float, bool]] = field(default_factory=list)
    raw_text: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return str(value).strip().casefold() if value is not None else ""


def _same_text(left: Any, right: Any) -> bool:
    return _clean(left) == _clean(right)


def score_document(
    *,
    doc_id: str,
    source: str,
    page: int | None,
    severity: str | None,
    layout: str | None,
    engine: str,
    latency_s: float,
    truth: Any,
    response: Any,
    truth_items: Sequence[Any],
    score_header: bool,
    score_page_count: bool = True,
    threshold: float = DEFAULT_THRESHOLD,
    raw_text: str | None = None,
) -> DocumentScore:
    """Bandingkan satu response dengan ground truth-nya.

    ``score_header`` mematikan penilaian field tingkat dokumen untuk halaman
    foto selain halaman pertama: kop surat memang hanya tercetak di halaman
    pertama, jadi menghukum halaman 2 karena tidak punya nomor dokumen akan
    salah menggambarkan model.

    ``score_page_count`` dimatikan untuk sumber foto. Satu berkas foto memang
    berisi satu halaman, jadi ``page_count=1`` adalah jawaban yang benar walau
    dokumen aslinya dua halaman — menilainya di sana mengukur cara evaluasi
    memotong dokumen, bukan kemampuan model.
    """
    predicted_items = list(response.items)
    parsed = bool(predicted_items) or (response.document_number or "") != ""

    score = DocumentScore(
        doc_id=doc_id,
        source=source,
        page=page,
        severity=severity,
        layout=layout,
        engine=engine,
        latency_s=latency_s,
        parsed=parsed,
        rows_truth=len(truth_items),
        rows_predicted=len(predicted_items),
        raw_text=raw_text,
    )

    if score_header:
        score.document_type_ok = response.document_type.value == truth.document_type.value
        score.document_number_ok = _same_text(response.document_number, truth.document_number)
        score.document_date_ok = response.document_date == truth.document_date
        score.sender_ok = similarity(response.sender, truth.sender) >= PARTY_THRESHOLD
        score.recipient_ok = similarity(response.recipient, truth.recipient) >= PARTY_THRESHOLD
        if score_page_count:
            score.page_count_ok = response.page_count == truth.page_count

    result: MatchResult = match_items(truth_items, predicted_items, threshold)
    score.rows_matched = len(result.matches)
    score.rows_exact_name = result.exact_matches

    item_confidences = list(response.confidence.items)

    for match in result.matches:
        expected = truth_items[match.truth_index]
        got = predicted_items[match.predicted_index]

        quantity_ok = expected.quantity == got.quantity
        score.quantity_ok += int(quantity_ok)
        score.unit_raw_ok += int(_same_text(expected.unit_raw, got.unit_raw))
        score.unit_normalized_ok += int(expected.unit_normalized == got.unit_normalized)
        score.quantity_per_unit_ok += int(expected.quantity_per_unit == got.quantity_per_unit)
        score.sku_ok += int(_same_text(expected.sku, got.sku))
        score.source_page_ok += int(expected.source_page == got.source_page)

        if match.predicted_index < len(item_confidences):
            # "Benar" di sini berarti nama dan jumlahnya benar — itulah yang
            # perlu diprediksi oleh confidence supaya berguna bagi operator.
            score.confidence_pairs.append(
                (item_confidences[match.predicted_index], match.exact and quantity_ok)
            )

    return score


# ---------------------------------------------------------------------------
# Agregasi
# ---------------------------------------------------------------------------


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


@dataclass
class Aggregate:
    label: str
    documents: int = 0
    parsed: int = 0
    latency_total: float = 0.0

    header_fields: dict[str, list[int]] = field(default_factory=dict)

    rows_truth: int = 0
    rows_predicted: int = 0
    rows_matched: int = 0
    rows_exact_name: int = 0

    field_totals: dict[str, int] = field(default_factory=dict)
    confidence_pairs: list[tuple[float, bool]] = field(default_factory=list)

    HEADER_FIELDS = (
        "document_type_ok",
        "document_number_ok",
        "document_date_ok",
        "sender_ok",
        "recipient_ok",
        "page_count_ok",
    )
    ITEM_FIELDS = (
        "quantity_ok",
        "unit_raw_ok",
        "unit_normalized_ok",
        "quantity_per_unit_ok",
        "sku_ok",
        "source_page_ok",
    )

    def add(self, score: DocumentScore) -> None:
        self.documents += 1
        self.parsed += int(score.parsed)
        self.latency_total += score.latency_s

        for name in self.HEADER_FIELDS:
            value = getattr(score, name)
            if value is None:
                continue
            bucket = self.header_fields.setdefault(name, [0, 0])
            bucket[0] += int(value)
            bucket[1] += 1

        self.rows_truth += score.rows_truth
        self.rows_predicted += score.rows_predicted
        self.rows_matched += score.rows_matched
        self.rows_exact_name += score.rows_exact_name

        for name in self.ITEM_FIELDS:
            self.field_totals[name] = self.field_totals.get(name, 0) + getattr(score, name)

        self.confidence_pairs.extend(score.confidence_pairs)

    # -- turunan ------------------------------------------------------------

    @property
    def parse_rate(self) -> float | None:
        return _ratio(self.parsed, self.documents)

    @property
    def recall(self) -> float | None:
        return _ratio(self.rows_matched, self.rows_truth)

    @property
    def precision(self) -> float | None:
        return _ratio(self.rows_matched, self.rows_predicted)

    @property
    def exact_name_rate(self) -> float | None:
        return _ratio(self.rows_exact_name, self.rows_truth)

    @property
    def mean_latency(self) -> float | None:
        return _ratio(self.latency_total, self.documents)

    def header_rate(self, name: str) -> float | None:
        bucket = self.header_fields.get(name)
        return _ratio(bucket[0], bucket[1]) if bucket else None

    def field_rate(self, name: str) -> float | None:
        """Penyebutnya baris terjodoh: 'dari yang ketemu, berapa yang benar'."""
        return _ratio(self.field_totals.get(name, 0), self.rows_matched)

    @property
    def confidence_split(self) -> tuple[float | None, float | None, int, int]:
        """Rata-rata confidence untuk baris benar vs salah.

        Kalau keduanya berdekatan, confidence tidak memprediksi apa pun dan
        tidak layak dipakai operator untuk memutuskan mana yang perlu dicek.
        """
        correct = [c for c, ok in self.confidence_pairs if ok]
        wrong = [c for c, ok in self.confidence_pairs if not ok]
        return (
            _ratio(sum(correct), len(correct)),
            _ratio(sum(wrong), len(wrong)),
            len(correct),
            len(wrong),
        )


def aggregate(scores: Iterable[DocumentScore], label: str = "keseluruhan") -> Aggregate:
    bucket = Aggregate(label=label)
    for score in scores:
        bucket.add(score)
    return bucket


def group_by(scores: Sequence[DocumentScore], attribute: str) -> dict[str, Aggregate]:
    groups: dict[str, Aggregate] = {}
    for score in scores:
        key = getattr(score, attribute) or "—"
        groups.setdefault(str(key), Aggregate(label=str(key))).add(score)
    return dict(sorted(groups.items()))
