"""Katalog kode warning Modul 3.

Konstanta, bukan string literal, supaya kode yang dipancarkan tidak pernah
berbeda dari yang tertulis di ``CONTRACT.md``. Laravel mencocokkan berdasarkan
``code``; isi ``message`` bebas berubah.
"""

from app.modules.crosscheck.schemas import CrossCheckWarning, Severity

IDENTITY_NOT_VERIFIED = "IDENTITY_NOT_VERIFIED"
INTEGRITY_NOT_VERIFIED = "INTEGRITY_NOT_VERIFIED"
PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
NO_COUNTABLE_ITEMS = "NO_COUNTABLE_ITEMS"
COUNT_POSSIBLY_UNDERSTATED = "COUNT_POSSIBLY_UNDERSTATED"
COUNT_UNRELIABLE_UPSTREAM = "COUNT_UNRELIABLE_UPSTREAM"
DOCUMENT_LOW_CONFIDENCE = "DOCUMENT_LOW_CONFIDENCE"
DOCUMENT_TYPE_UNKNOWN = "DOCUMENT_TYPE_UNKNOWN"
NO_OBJECT_DETECTED_UPSTREAM = "NO_OBJECT_DETECTED_UPSTREAM"


def warning(
    code: str,
    message: str,
    severity: Severity = Severity.WARNING,
    item_index: int | None = None,
) -> CrossCheckWarning:
    return CrossCheckWarning(
        code=code, message=message, severity=severity, item_index=item_index
    )


def identity_not_verified() -> CrossCheckWarning:
    return warning(
        IDENTITY_NOT_VERIFIED,
        "Identitas produk tidak diverifikasi: model vision hanya mengenali satu kelas, "
        "sehingga ia tahu ada berapa kardus tetapi tidak tahu kardus apa.",
        Severity.INFO,
    )


def integrity_not_verified() -> CrossCheckWarning:
    return warning(
        INTEGRITY_NOT_VERIFIED,
        "Integritas fisik belum diperiksa: model deteksi kerusakan belum tersedia. "
        "Ini bukan pernyataan bahwa kemasan aman.",
        Severity.INFO,
    )


def partial_coverage(item_index: int, item_name: str, unit_raw: str) -> CrossCheckWarning:
    return warning(
        PARTIAL_COVERAGE,
        f"'{item_name}' ({unit_raw}) tidak ikut diverifikasi karena satuannya tidak "
        "terlihat sebagai kardus oleh kamera.",
        Severity.WARNING,
        item_index,
    )


def no_countable_items() -> CrossCheckWarning:
    return warning(
        NO_COUNTABLE_ITEMS,
        "Tidak ada baris bersatuan kardus di dokumen, sehingga kuantitas tidak bisa "
        "diverifikasi secara visual sama sekali.",
        Severity.ERROR,
    )


def count_possibly_understated(shortfall: int) -> CrossCheckWarning:
    return warning(
        COUNT_POSSIBLY_UNDERSTATED,
        f"Fisik kurang {shortfall} dari dokumen, tetapi Modul 2 mendeteksi tumpukan "
        "bertindihan — sebagian selisih ini mungkin kemasan yang terhalang, bukan barang "
        "yang benar-benar tidak ada.",
        Severity.WARNING,
    )


def count_unreliable_upstream() -> CrossCheckWarning:
    return warning(
        COUNT_UNRELIABLE_UPSTREAM,
        "Modul 2 menandai hitungannya tidak dapat diandalkan, jadi angka itu tidak dipakai "
        "untuk memvonis. Perlu foto ulang atau perhitungan manual.",
        Severity.ERROR,
    )


def document_low_confidence(item_index: int, item_name: str) -> CrossCheckWarning:
    return warning(
        DOCUMENT_LOW_CONFIDENCE,
        f"'{item_name}' ikut dijumlahkan, tetapi Modul 1 membacanya dengan confidence "
        "rendah — angka dokumennya sendiri belum tentu benar.",
        Severity.WARNING,
        item_index,
    )


def document_type_unknown() -> CrossCheckWarning:
    return warning(
        DOCUMENT_TYPE_UNKNOWN,
        "Modul 1 tidak mengenali jenis dokumen ini sebagai Surat Jalan maupun Invoice.",
        Severity.WARNING,
    )


def no_object_detected_upstream() -> CrossCheckWarning:
    return warning(
        NO_OBJECT_DETECTED_UPSTREAM,
        "Modul 2 tidak menemukan objek apa pun di foto.",
        Severity.ERROR,
    )
