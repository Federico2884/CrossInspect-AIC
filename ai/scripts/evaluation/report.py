"""Menyusun laporan evaluasi dalam Markdown berbahasa Indonesia.

Laporan ini dibaca manusia yang harus memutuskan apakah model layak dipakai,
jadi urutannya mengikuti pertanyaan yang benar-benar ditanyakan: apakah
keluarannya terbaca, apakah barisnya ketemu, apakah angkanya benar, dan
seberapa mahal foto yang jelek.
"""

from __future__ import annotations

from collections.abc import Sequence

from scripts.evaluation.metrics import Aggregate, DocumentScore, aggregate, group_by

FIELD_LABELS = {
    "quantity_ok": "Jumlah",
    "unit_raw_ok": "Satuan (apa adanya)",
    "unit_normalized_ok": "Satuan (normalisasi)",
    "quantity_per_unit_ok": "Isi per satuan",
    "sku_ok": "SKU",
    "source_page_ok": "Halaman asal",
}

HEADER_LABELS = {
    "document_type_ok": "Jenis dokumen",
    "document_number_ok": "Nomor dokumen",
    "document_date_ok": "Tanggal",
    "sender_ok": "Pengirim",
    "recipient_ok": "Penerima",
    "page_count_ok": "Jumlah halaman",
}


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _rows_table(buckets: Sequence[Aggregate]) -> list[str]:
    lines = [
        "| Kelompok | Dokumen | JSON terbaca | Recall baris | Presisi baris | Nama persis |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket in buckets:
        lines.append(
            f"| {bucket.label} | {bucket.documents} | {pct(bucket.parse_rate)} | "
            f"{pct(bucket.recall)} | {pct(bucket.precision)} | {pct(bucket.exact_name_rate)} |"
        )
    return lines


def _fields_table(buckets: Sequence[Aggregate]) -> list[str]:
    header = "| Field | " + " | ".join(b.label for b in buckets) + " |"
    divider = "|---|" + "---:|" * len(buckets)
    lines = [header, divider]
    for name, label in FIELD_LABELS.items():
        cells = " | ".join(pct(b.field_rate(name)) for b in buckets)
        lines.append(f"| {label} | {cells} |")
    return lines


def _header_table(buckets: Sequence[Aggregate]) -> list[str]:
    header = "| Field | " + " | ".join(b.label for b in buckets) + " |"
    divider = "|---|" + "---:|" * len(buckets)
    lines = [header, divider]
    for name, label in HEADER_LABELS.items():
        cells = " | ".join(pct(b.header_rate(name)) for b in buckets)
        lines.append(f"| {label} | {cells} |")
    return lines


def render(scores: Sequence[DocumentScore], engine: str, threshold: float) -> str:
    overall = aggregate(scores)
    by_source = list(group_by(scores, "source").values())
    by_severity = list(group_by(scores, "severity").values())

    correct_conf, wrong_conf, n_correct, n_wrong = overall.confidence_split

    lines: list[str] = [
        "# Evaluasi Modul 1 — Document Parsing",
        "",
        f"Engine: `{engine}` · {overall.documents} panggilan · "
        f"{overall.rows_truth} baris ground truth · "
        f"rata-rata {overall.mean_latency:.1f} detik per panggilan"
        if overall.mean_latency is not None
        else f"Engine: `{engine}` · {overall.documents} panggilan",
        "",
        "Dihasilkan otomatis oleh `scripts/evaluate.py`. Jangan disunting tangan —",
        "jalankan ulang harness-nya.",
        "",
        "## Ringkasan",
        "",
        f"- **JSON terbaca**: {pct(overall.parse_rate)} panggilan menghasilkan keluaran "
        "yang bisa diurai.",
        f"- **Recall baris**: {pct(overall.recall)} baris ground truth berhasil ditemukan.",
        f"- **Presisi baris**: {pct(overall.precision)} baris yang dikembalikan model "
        "benar-benar ada di dokumen.",
        f"- **Jumlah benar**: {pct(overall.field_rate('quantity_ok'))} dari baris yang "
        "ketemu punya jumlah yang tepat.",
        "",
        "Angka **jumlah** adalah yang paling menentukan. Nama barang yang salah ketik masih",
        "kelihatan oleh manusia; jumlah yang salah lolos begitu saja dan merusak cross-check.",
        "",
        "## Menemukan baris",
        "",
        f"Penjodohan memakai kemiripan nama dengan ambang {threshold:.2f}. Kolom "
        "*Nama persis* menghitung baris yang namanya sama tepat setelah normalisasi;",
        "selisihnya terhadap *Recall* adalah baris yang terbaca tetapi ditulis sedikit berbeda.",
        "",
        *_rows_table([overall, *by_source]),
        "",
        "## Ketepatan isi baris",
        "",
        "Penyebutnya adalah baris yang berhasil dijodohkan — jadi ini menjawab "
        "\"dari yang ketemu, berapa yang dibaca dengan benar\".",
        "",
        *_fields_table([overall, *by_source]),
        "",
        "## Field tingkat dokumen",
        "",
        "Hanya dinilai pada panggilan yang memang memuat kop surat (PDF utuh, atau "
        "halaman pertama untuk sumber foto).",
        "",
        *_header_table([overall, *by_source]),
        "",
        "## Pengaruh kualitas gambar",
        "",
        "`—` berarti dokumen bersih tanpa degradasi.",
        "",
        *_rows_table(by_severity),
        "",
        *_fields_table(by_severity),
        "",
        "## Apakah confidence bisa dipercaya?",
        "",
        f"Rata-rata confidence baris **benar**: {pct(correct_conf)} (n={n_correct}) · "
        f"baris **salah**: {pct(wrong_conf)} (n={n_wrong})",
        "",
    ]

    if correct_conf is None or wrong_conf is None:
        lines.append(
            "Belum cukup data untuk menilai kalibrasi — perlu baris benar *dan* salah."
        )
    else:
        gap = correct_conf - wrong_conf
        if gap >= 0.10:
            lines.append(
                f"Selisihnya {gap * 100:.1f} poin: confidence cukup memisahkan benar dari "
                "salah, jadi ambang LOW_CONFIDENCE_ITEM masuk akal dipakai operator."
            )
        else:
            lines.append(
                f"Selisihnya hanya {gap * 100:.1f} poin. Confidence nyaris tidak membedakan "
                "baris benar dari baris salah, jadi angka itu **belum layak** dipakai untuk "
                "memutuskan baris mana yang perlu diperiksa manusia. Perlu ditinjau ulang "
                "sebelum UI menyandarkan apa pun padanya."
            )

    lines.extend(["", "## Catatan", "", *_caveats(scores)])
    return "\n".join(lines) + "\n"


def _caveats(scores: Sequence[DocumentScore]) -> list[str]:
    doc_ids = {score.doc_id for score in scores}
    return [
        f"- Sampel: {len(doc_ids)} dokumen, {len(scores)} panggilan engine. "
        "Dataset penuh berisi 200 dokumen; jalankan tanpa `--sample` untuk seluruhnya.",
        "- Penjodohan baris memakai kemiripan teks, bukan pemahaman makna. Dua produk "
        "dengan nama sangat mirip berpotensi tertukar.",
        "- Satuan pada dataset sintetis sengaja diacak (mis. minyak goreng dalam 'Zak'), "
        "sehingga model tidak bisa menebak satuan dari pengetahuan umum. Itu memang "
        "disengaja, tetapi membuat angka satuan lebih pesimistis daripada dokumen nyata.",
    ]
