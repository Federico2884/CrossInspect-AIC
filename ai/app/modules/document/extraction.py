"""Ubah keluaran mentah model menjadi ``ParseResponse``.

Tidak ada torch di sini. Semua yang rapuh — JSON yang tidak taat format,
tanggal gaya Indonesia, aritmetika satuan, perhitungan confidence — dikerjakan
di modul ini supaya bisa diuji tanpa memuat model 4 GB.

Prinsip yang dipegang: **kegagalan membaca bukan kegagalan request**.
``CONTRACT.md`` menjanjikan dokumen yang parse-nya buruk tetap dijawab 200
beserta ``warnings[]``. Jadi fungsi di sini tidak melempar saat model
mengarang; yang terburuk terjadi adalah dokumen dinyatakan ``UNKNOWN``
lengkap dengan warning-nya.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from app.core.config import get_settings
from app.modules.document import warnings as w
from app.modules.document.schemas import (
    Confidence,
    DocumentType,
    Item,
    Meta,
    ParseResponse,
    ParseWarning,
    Severity,
)
from app.modules.document.units import normalize_unit

MONTHS_ID = (
    "januari",
    "februari",
    "maret",
    "april",
    "mei",
    "juni",
    "juli",
    "agustus",
    "september",
    "oktober",
    "november",
    "desember",
)

# Generator step 3 mencetak tiga gaya: 12-08-2026, 12/08/2026, "12 Agustus 2026".
# Ketiganya hari-dulu. Ini bukan detail sepele: 12/08 harus jadi 12 Agustus,
# bukan 8 Desember.
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")
_TEXT_DATE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class TokenSpan:
    """Satu token beserta posisinya di teks hasil decode."""

    start: int
    end: int
    probability: float


@dataclass
class ExtractedPage:
    """Hasil baca satu halaman. Penggabungan antar halaman terjadi di engine."""

    ok: bool
    raw_text: str
    document_type: DocumentType | None = None
    document_number: str | None = None
    document_date: date | None = None
    sender: str | None = None
    recipient: str | None = None
    items: list[Item] = field(default_factory=list)
    # Skor yang masuk kontrak: peluang token TERLEMAH pada rentang nama barang.
    # Dipilih lewat pengukuran, bukan selera — pada 845 baris, rata-rata hanya
    # memisahkan baris benar dari salah sejauh 4,4 poin, sedangkan token
    # terlemah memisahkan 18,2 poin.
    item_confidences: list[float] = field(default_factory=list)
    document_number_confidence: float = 0.0
    # Kandidat pembanding, tidak masuk kontrak. Tetap dikumpulkan supaya
    # evaluasi berikutnya bisa menilai ulang ketiganya tanpa inference ulang.
    item_confidences_mean: list[float] = field(default_factory=list)
    item_confidences_quantity: list[float] = field(default_factory=list)


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------


def build_token_spans(pieces: Sequence[str], probabilities: Sequence[float]) -> list[TokenSpan]:
    """Rangkai offset karakter tiap token dari potongan teks hasil decode.

    ``pieces`` harus token yang bila disambung persis membentuk teks utuh —
    itulah yang membuat offset-nya bisa dipercaya.
    """
    spans: list[TokenSpan] = []
    cursor = 0
    for piece, probability in zip(pieces, probabilities, strict=False):
        length = len(piece)
        spans.append(TokenSpan(cursor, cursor + length, probability))
        cursor += length
    return spans


def span_confidence(spans: Sequence[TokenSpan], start: int, end: int) -> float:
    """Rata-rata peluang token yang bersinggungan dengan rentang [start, end).

    Rentang kosong atau tanpa token yang cocok menghasilkan 0.0 — lebih jujur
    daripada mengarang angka tinggi untuk sesuatu yang tidak bisa ditelusuri.
    """
    if end <= start:
        return 0.0

    hits = [span.probability for span in spans if span.start < end and span.end > start]
    if not hits:
        return 0.0
    return max(0.0, min(1.0, sum(hits) / len(hits)))


def span_confidence_min(spans: Sequence[TokenSpan], start: int, end: int) -> float:
    """Peluang token **terlemah** dalam rentang.

    Alternatif dari rata-rata. Pada nama panjang, satu token ragu tenggelam
    oleh belasan token yakin — padahal justru token ragu itu yang menandakan
    barisnya perlu diperiksa. Dipakai sebagai kandidat pembanding; mana yang
    benar-benar memisahkan baris benar dari salah baru bisa dinilai setelah
    evaluasi penuh mengumpulkan cukup banyak baris salah.
    """
    if end <= start:
        return 0.0

    hits = [span.probability for span in spans if span.start < end and span.end > start]
    if not hits:
        return 0.0
    return max(0.0, min(1.0, min(hits)))


def confidence_for_value(text: str, spans: Sequence[TokenSpan], value: str | None) -> float:
    """Cari nilai di teks lalu hitung confidence token yang menuliskannya."""
    if not value:
        return 0.0
    index = text.find(str(value))
    if index < 0:
        return 0.0
    return span_confidence(spans, index, index + len(str(value)))


def confidence_for_value_min(text: str, spans: Sequence[TokenSpan], value: str | None) -> float:
    """Seperti ``confidence_for_value``, tetapi memakai token terlemah."""
    if not value:
        return 0.0
    index = text.find(str(value))
    if index < 0:
        return 0.0
    return span_confidence_min(spans, index, index + len(str(value)))


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------

_TRAILING_COMMA = re.compile(r",+\s*([}\]])")
_UNQUOTED_VALUE = re.compile(
    r'(:\s*)([A-Za-z0-9_.\-@/()]+(?:\s+[A-Za-z0-9_.\-@/()]+)*)(\s*[,}\]])'
)


def _repair_json_string(text: str) -> str:
    """Perbaiki kebiasaan sintaks JSON yang cacat dari model LLM/VLM."""
    cleaned = _TRAILING_COMMA.sub(r"\1", text)

    def _quote_unquoted(match: re.Match) -> str:
        prefix, val, suffix = match.group(1), match.group(2).strip(), match.group(3)
        if val in {"true", "false", "null"}:
            return f"{prefix}{val}{suffix}"
        if re.match(r"^-?\d+(?:\.\d+)?$", val):
            return f"{prefix}{val}{suffix}"
        return f'{prefix}"{val}"{suffix}'

    cleaned = _UNQUOTED_VALUE.sub(_quote_unquoted, cleaned)
    return cleaned


def _close_truncated_json(text: str) -> str:
    """Tutup kurung/petik yang terpotong bila keluaran terputus di tengah jalan."""
    stack: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]" and stack and stack[-1] == char:
            stack.pop()

    result = text
    if in_string:
        result += '"'
    while stack:
        result += stack.pop()
    return result


def _try_parse_python_dict(text: str) -> dict | None:
    """Coba uraikan kamus gaya Python (petik tunggal, None, True, False)."""
    converted = re.sub(r"\bnull\b", "None", text)
    converted = re.sub(r"\btrue\b", "True", converted)
    converted = re.sub(r"\bfalse\b", "False", converted)
    try:
        parsed = ast.literal_eval(converted)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return None


def _salvage_partial_payload(text: str) -> dict | None:
    """Penyelamatan darurat bila seluruh JSON tidak dapat diurai utuh.

    Mengekstrak metadata dokumen dan baris barang secara modular agar baris
    yang terbaca dengan benar tidak terbuang hanya karena satu bagian JSON rusak.
    """
    if not text or "{" not in text:
        return None

    # Cari metadata tingkat dokumen
    doc_type_m = re.search(
        r'"(?:document_type|jenis_dokumen)"\s*:\s*"([^"]+)"', text, re.IGNORECASE
    )
    doc_num_m = re.search(
        r'"(?:document_number|nomor_dokumen)"\s*:\s*"([^"]+)"', text, re.IGNORECASE
    )
    doc_date_m = re.search(
        r'"(?:document_date|tanggal)"\s*:\s*"([^"]+)"', text, re.IGNORECASE
    )
    sender_m = re.search(r'"(?:sender|pengirim)"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
    recipient_m = re.search(r'"(?:recipient|penerima)"\s*:\s*"([^"]+)"', text, re.IGNORECASE)

    # Cari blok barang individual
    item_blocks = re.findall(
        r'\{[^{}]*(?:"item_name"|"nama_barang")[^{}]*\}', text, re.IGNORECASE
    )
    items: list[dict] = []

    for block in item_blocks:
        parsed_item = None
        for candidate_block in (block, _repair_json_string(block)):
            try:
                p = json.loads(candidate_block)
                if isinstance(p, dict):
                    parsed_item = p
                    break
            except json.JSONDecodeError:
                continue

        if parsed_item is None:
            name_m = re.search(
                r'"(?:item_name|nama_barang|name)"\s*:\s*"([^"]+)"', block, re.IGNORECASE
            )
            if not name_m:
                continue
            sku_m = re.search(
                r'"(?:sku|kode|kode_barang)"\s*:\s*"([^"]+)"', block, re.IGNORECASE
            )
            qty_m = re.search(
                r'"(?:quantity|jumlah)"\s*:\s*"?([^",}\s]+)"?', block, re.IGNORECASE
            )
            unit_m = re.search(
                r'"(?:unit_raw|satuan|unit)"\s*:\s*"([^"]+)"', block, re.IGNORECASE
            )
            qpu_m = re.search(
                r'"(?:quantity_per_unit|isi_per_satuan)"\s*:\s*"?([^",}\s]+)"?',
                block,
                re.IGNORECASE,
            )

            parsed_item = {
                "item_name": name_m.group(1) if name_m else None,
                "sku": sku_m.group(1) if sku_m else None,
                "quantity": qty_m.group(1) if qty_m else None,
                "unit_raw": unit_m.group(1) if unit_m else None,
                "quantity_per_unit": qpu_m.group(1) if qpu_m else None,
            }

        if parsed_item and (parsed_item.get("item_name") or parsed_item.get("nama_barang")):
            items.append(parsed_item)

    has_meta = any([doc_type_m, doc_num_m, doc_date_m, sender_m, recipient_m])
    if not items and not has_meta:
        return None

    salvaged: dict = {}
    if doc_type_m:
        salvaged["document_type"] = doc_type_m.group(1)
    if doc_num_m:
        salvaged["document_number"] = doc_num_m.group(1)
    if doc_date_m:
        salvaged["document_date"] = doc_date_m.group(1)
    if sender_m:
        salvaged["sender"] = sender_m.group(1)
    if recipient_m:
        salvaged["recipient"] = recipient_m.group(1)
    salvaged["items"] = items

    return salvaged


def _is_root_payload(data: dict) -> bool:
    """Pastikan kamus adalah dokumen tingkat atas, bukan hanya satu baris barang."""
    root_keys = {
        "document_type",
        "jenis_dokumen",
        "document_number",
        "nomor_dokumen",
        "document_date",
        "tanggal",
        "sender",
        "pengirim",
        "recipient",
        "penerima",
        "items",
        "barang",
    }
    return any(key in data for key in root_keys)


def extract_json_object(text: str) -> dict | None:
    """Ambil objek JSON pertama dari keluaran model, dengan toleransi sintaks.

    Model kerap membungkus jawaban dengan pagar markdown, menambah kalimat
    penutup, koma gantung, nilai tak terkutip, atau output terpotong.
    Semua hal tersebut diperbaiki dan diselamatkan bila memungkinkan.
    """
    if not text:
        return None

    fenced = _FENCE.search(text)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)

    for candidate in candidates:
        block = _first_balanced_object(candidate)
        blocks_to_try: list[str] = []
        if block is not None:
            blocks_to_try.append(block)
        else:
            start = candidate.find("{")
            if start >= 0:
                blocks_to_try.append(candidate[start:])

        for raw_block in blocks_to_try:
            try:
                parsed = json.loads(raw_block)
                if isinstance(parsed, dict) and _is_root_payload(parsed):
                    return parsed
            except json.JSONDecodeError:
                pass

            repaired = _repair_json_string(raw_block)
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, dict) and _is_root_payload(parsed):
                    return parsed
            except json.JSONDecodeError:
                pass

            closed = _close_truncated_json(repaired)
            try:
                parsed = json.loads(closed)
                if isinstance(parsed, dict) and _is_root_payload(parsed):
                    return parsed
            except json.JSONDecodeError:
                pass

            parsed_py = _try_parse_python_dict(raw_block)
            if parsed_py is not None and _is_root_payload(parsed_py):
                return parsed_py

    return _salvage_partial_payload(text)


def _first_balanced_object(text: str) -> str | None:
    """Potong ``{...}`` pertama yang kurungnya seimbang, mengabaikan isi string."""
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


# --------------------------------------------------------------------------
# Koersi nilai
# --------------------------------------------------------------------------


def coerce_int(value: object) -> int | None:
    """Angka dari model bisa berupa '1.200', '12 pcs', atau 12.0."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else int(round(value))
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if digits:
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def parse_indonesian_date(value: object) -> date | None:
    """Tanggal gaya dokumen Indonesia -> ``date``. Hari selalu di depan."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()

    iso = _ISO_DATE.search(text)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        return _safe_date(year, month, day)

    textual = _TEXT_DATE.search(text)
    if textual:
        day_str, month_name, year_str = textual.groups()
        month_key = month_name.strip().lower()
        for index, name in enumerate(MONTHS_ID, start=1):
            if month_key.startswith(name[:3]):
                return _safe_date(int(year_str), index, int(day_str))

    numeric = _NUMERIC_DATE.search(text)
    if numeric:
        day_str, month_str, year_str = numeric.groups()
        year = int(year_str)
        if year < 100:
            year += 2000
        return _safe_date(year, int(month_str), int(day_str))

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "-", "n/a", "tidak ada"}:
        return None
    return text


def _document_type(value: object) -> DocumentType | None:
    text = _clean_str(value)
    if text is None:
        return None
    key = text.strip().upper().replace(" ", "_").replace("-", "_")
    if key in DocumentType.__members__:
        return DocumentType[key]
    if "SURAT" in key or "JALAN" in key or key in {"DO", "DELIVERY_ORDER"}:
        return DocumentType.SURAT_JALAN
    if "INVOICE" in key or "FAKTUR" in key:
        return DocumentType.INVOICE
    return DocumentType.UNKNOWN


# --------------------------------------------------------------------------
# Halaman -> struktur
# --------------------------------------------------------------------------


def build_item(row: object, source_page: int) -> Item | None:
    """Satu baris barang. Baris tanpa nama atau tanpa jumlah dibuang.

    Membuang lebih aman daripada menebak: baris setengah terbaca yang lolos
    akan dihitung Modul 2 sebagai barang yang benar-benar ada.
    """
    if not isinstance(row, dict):
        return None

    name = _clean_str(row.get("item_name") or row.get("nama_barang") or row.get("name"))
    if not name:
        return None

    quantity = coerce_int(row.get("quantity", row.get("jumlah")))
    if quantity is None or quantity < 0:
        return None

    unit_raw = _clean_str(row.get("unit_raw") or row.get("satuan") or row.get("unit")) or ""
    per_unit = coerce_int(row.get("quantity_per_unit", row.get("isi_per_satuan")))
    if per_unit is not None and per_unit < 1:
        per_unit = None

    try:
        return Item(
            item_name=name,
            sku=_clean_str(row.get("sku")),
            quantity=quantity,
            unit_raw=unit_raw,
            unit_normalized=normalize_unit(unit_raw),
            quantity_per_unit=per_unit,
            source_page=source_page,
        )
    except ValueError:
        # Nilai lolos koersi tapi ditolak kontrak — perlakukan seperti baris rusak.
        return None


def extract_page(
    raw_text: str,
    source_page: int,
    spans: Sequence[TokenSpan] | None = None,
) -> ExtractedPage:
    """Keluaran model untuk satu halaman -> struktur, tanpa pernah melempar."""
    spans = spans or []
    payload = extract_json_object(raw_text)
    if payload is None:
        return ExtractedPage(ok=False, raw_text=raw_text)

    rows = payload.get("items") or payload.get("barang") or []
    if not isinstance(rows, list):
        rows = []

    items: list[Item] = []
    confidences: list[float] = []
    confidences_mean: list[float] = []
    confidences_qty: list[float] = []
    for row in rows:
        item = build_item(row, source_page)
        if item is None:
            continue
        items.append(item)
        # Token terlemah, bukan rata-rata: satu token ragu di tengah nama
        # panjang tenggelam bila dirata-rata, padahal justru token itulah
        # tanda barisnya perlu diperiksa.
        confidences.append(confidence_for_value_min(raw_text, spans, item.item_name))
        confidences_mean.append(confidence_for_value(raw_text, spans, item.item_name))
        # Rentang jumlah. Diduga paling relevan karena "benar" pada evaluasi
        # berarti nama DAN jumlah benar — ternyata justru pemisah terburuk
        # (2,3 poin). Disimpan sebagai pembanding.
        confidences_qty.append(confidence_for_value(raw_text, spans, str(item.quantity)))

    number = _clean_str(payload.get("document_number") or payload.get("nomor_dokumen"))

    return ExtractedPage(
        ok=True,
        raw_text=raw_text,
        document_type=_document_type(payload.get("document_type") or payload.get("jenis_dokumen")),
        document_number=number,
        document_date=parse_indonesian_date(
            payload.get("document_date") or payload.get("tanggal")
        ),
        sender=_clean_str(payload.get("sender") or payload.get("pengirim")),
        recipient=_clean_str(payload.get("recipient") or payload.get("penerima")),
        items=items,
        item_confidences=confidences,
        item_confidences_mean=confidences_mean,
        item_confidences_quantity=confidences_qty,
        # Definisi yang sama dipakai lintas field supaya satu angka berarti
        # satu hal. Kalibrasi khusus nomor dokumen BELUM pernah diukur —
        # evaluasi hanya menilai baris barang — jadi ini konsistensi, bukan
        # bukti.
        document_number_confidence=confidence_for_value_min(raw_text, spans, number),
    )


# --------------------------------------------------------------------------
# Gabungan -> response
# --------------------------------------------------------------------------

def low_confidence_threshold() -> float:
    """Ambang LOW_CONFIDENCE_ITEM, bisa disetel lewat ``AI_LOW_CONFIDENCE_THRESHOLD``.

    Dibaca saat dipakai, bukan sebagai konstanta modul, supaya nilainya bisa
    dikalibrasi ulang dari environment setelah evaluasi penuh tanpa menyentuh
    kode. Lihat catatan panjang di ``config.py`` soal kenapa 0.55 diganti.
    """
    return get_settings().low_confidence_threshold


def assemble_response(
    pages: Sequence[ExtractedPage],
    page_count: int,
    truncated: bool,
    total_pages: int,
    engine_name: str,
) -> ParseResponse:
    """Gabungkan hasil per halaman menjadi satu response yang sah.

    Field tingkat dokumen diambil dari halaman pertama yang berhasil
    memberikannya — pada surat jalan multi-halaman, kop biasanya hanya ada di
    halaman pertama, sedangkan barang tersebar.
    """
    warnings: list[ParseWarning] = []
    threshold = low_confidence_threshold()

    items: list[Item] = []
    item_confidences: list[float] = []
    for page in pages:
        items.extend(page.items)
        item_confidences.extend(page.item_confidences)

    def first(attribute: str):
        for page in pages:
            value = getattr(page, attribute)
            if value:
                return value
        return None

    document_type = first("document_type") or DocumentType.UNKNOWN
    document_number = first("document_number") or ""
    document_date = first("document_date")
    number_confidence = max((page.document_number_confidence for page in pages), default=0.0)

    if not any(page.ok for page in pages):
        document_type = DocumentType.UNKNOWN
        warnings.append(
            w.warning(
                w.UNRECOGNISED_DOCUMENT_TYPE,
                "Model tidak mengembalikan JSON yang bisa dibaca; dokumen tidak dikenali.",
                Severity.ERROR,
            )
        )

    if not document_number:
        warnings.append(
            w.warning(w.MISSING_FIELD, "Nomor dokumen tidak terbaca.", Severity.WARNING)
        )
    if document_date is None:
        warnings.append(
            w.warning(w.MISSING_DOCUMENT_DATE, "Tanggal dokumen tidak ditemukan.", Severity.WARNING)
        )

    for index, (item, score) in enumerate(zip(items, item_confidences, strict=False)):
        if score < threshold:
            warnings.append(
                w.warning(
                    w.LOW_CONFIDENCE_ITEM,
                    f"Baris '{item.item_name}' terbaca dengan keyakinan rendah; mohon konfirmasi.",
                    Severity.WARNING,
                    item_index=index,
                )
            )
        if item.unit_normalized.value == "unknown" and item.unit_raw:
            warnings.append(
                w.warning(
                    w.AMBIGUOUS_UNIT,
                    f"Satuan '{item.unit_raw}' di luar daftar normalisasi; unit_raw dipertahankan.",
                    Severity.WARNING,
                    item_index=index,
                )
            )

    if truncated:
        warnings.append(
            w.warning(
                w.PAGE_LIMIT_TRUNCATED,
                f"Dokumen memiliki {total_pages} halaman; hanya {page_count} pertama yang dibaca.",
                Severity.WARNING,
            )
        )

    overall = _overall_confidence(number_confidence, item_confidences, any(p.ok for p in pages))

    return ParseResponse(
        document_type=document_type,
        document_number=document_number,
        document_date=document_date,
        sender=first("sender"),
        recipient=first("recipient"),
        page_count=page_count,
        items=items,
        confidence=Confidence(
            document_number=number_confidence,
            items=item_confidences,
            overall=overall,
        ),
        warnings=warnings,
        meta=Meta(engine=engine_name, device="cpu", processing_ms=0, scenario=None),
    )


def _overall_confidence(
    number_confidence: float, item_confidences: Sequence[float], parsed: bool
) -> float:
    if not parsed:
        return 0.0
    scores = [number_confidence, *item_confidences]
    scores = [score for score in scores if score > 0.0]
    if not scores:
        return 0.0
    return max(0.0, min(1.0, sum(scores) / len(scores)))
