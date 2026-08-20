"""Katalog kode warning Modul 1.

Konstanta, bukan string literal, supaya engine mock dan engine asli nanti
memancarkan kode yang identik — Laravel mencocokkan berdasarkan ``code``,
sedangkan ``message`` bebas berubah.
"""

from app.modules.document.schemas import ParseWarning, Severity

LOW_CONFIDENCE_ITEM = "LOW_CONFIDENCE_ITEM"
MISSING_DOCUMENT_DATE = "MISSING_DOCUMENT_DATE"
MISSING_FIELD = "MISSING_FIELD"
AMBIGUOUS_UNIT = "AMBIGUOUS_UNIT"
UNRECOGNISED_DOCUMENT_TYPE = "UNRECOGNISED_DOCUMENT_TYPE"
PAGE_LIMIT_TRUNCATED = "PAGE_LIMIT_TRUNCATED"
QUANTITY_MISMATCH = "QUANTITY_MISMATCH"


def warning(
    code: str,
    message: str,
    severity: Severity = Severity.WARNING,
    item_index: int | None = None,
) -> ParseWarning:
    return ParseWarning(code=code, message=message, severity=severity, item_index=item_index)
