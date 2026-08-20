"""Render DocumentSpec menjadi PDF memakai ReportLab.

Memakai ``canvas`` level rendah, bukan Platypus, karena paginasi harus
dikendalikan manual: ``source_page`` pada ground truth wajib sama persis
dengan halaman tempat barang itu benar-benar tercetak.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from scripts.synthetic.document import DocumentSpec, format_date

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm


def _draw_header(pdf: canvas.Canvas, spec: DocumentSpec, page: int) -> float:
    """Gambar kop surat. Kembalikan posisi Y untuk konten berikutnya."""
    truth = spec.truth
    labels = spec.labels
    top = PAGE_HEIGHT - MARGIN

    if spec.layout == "boxed":
        pdf.setLineWidth(1)
        pdf.rect(MARGIN, top - 42 * mm, PAGE_WIDTH - 2 * MARGIN, 42 * mm)

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(MARGIN + 3 * mm, top - 7 * mm, truth.sender or "")
    pdf.setFont("Helvetica", 7)
    pdf.drawString(MARGIN + 3 * mm, top - 11 * mm, spec.sender_address[:88])

    title_size = 15 if spec.layout != "minimal" else 13
    pdf.setFont("Helvetica-Bold", title_size)
    if spec.layout == "minimal":
        pdf.drawString(MARGIN + 3 * mm, top - 22 * mm, spec.title)
    else:
        pdf.drawCentredString(PAGE_WIDTH / 2, top - 22 * mm, spec.title)

    if spec.layout == "classic":
        pdf.setLineWidth(0.8)
        pdf.line(MARGIN, top - 25 * mm, PAGE_WIDTH - MARGIN, top - 25 * mm)

    # Blok nomor/tanggal di kanan, penerima di kiri — tata letak paling umum.
    right_x = PAGE_WIDTH - MARGIN - 62 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(right_x, top - 31 * mm, f"{labels['number']}")
    pdf.drawString(right_x + 28 * mm, top - 31 * mm, f": {truth.document_number}")
    pdf.drawString(right_x, top - 35 * mm, f"{labels['date']}")
    pdf.drawString(
        right_x + 28 * mm,
        top - 35 * mm,
        f": {format_date(truth.document_date, spec.date_format)}" if truth.document_date else ": -",
    )

    pdf.drawString(MARGIN + 3 * mm, top - 31 * mm, f"{labels['recipient']}")
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(MARGIN + 3 * mm, top - 35 * mm, truth.recipient or "")
    pdf.setFont("Helvetica", 7)
    pdf.drawString(MARGIN + 3 * mm, top - 39 * mm, spec.recipient_address[:70])

    if truth.page_count > 1:
        pdf.setFont("Helvetica-Oblique", 7)
        pdf.drawRightString(
            PAGE_WIDTH - MARGIN, top - 44 * mm, f"Halaman {page} dari {truth.page_count}"
        )

    return top - 50 * mm


def _draw_table(pdf: canvas.Canvas, spec: DocumentSpec, items, start_y: float) -> float:
    columns = (
        (MARGIN + 2 * mm, "No"),
        (MARGIN + 10 * mm, spec.labels["sku"]),
        (MARGIN + 34 * mm, spec.labels["item"]),
        (PAGE_WIDTH - MARGIN - 42 * mm, spec.labels["qty"]),
        (PAGE_WIDTH - MARGIN - 28 * mm, spec.labels["unit"]),
        (PAGE_WIDTH - MARGIN - 14 * mm, "Ket."),
    )
    row_height = 7 * mm
    header_y = start_y

    if spec.layout == "boxed":
        pdf.setFillGray(0.85)
        pdf.rect(MARGIN, header_y - 2 * mm, PAGE_WIDTH - 2 * MARGIN, row_height, fill=1, stroke=0)
        pdf.setFillGray(0)

    pdf.setFont("Helvetica-Bold", 8)
    for x, label in columns:
        pdf.drawString(x, header_y, label)

    if spec.layout != "minimal":
        pdf.setLineWidth(0.6)
        pdf.line(MARGIN, header_y - 2.5 * mm, PAGE_WIDTH - MARGIN, header_y - 2.5 * mm)

    pdf.setFont("Helvetica", 8)
    y = header_y - row_height
    for offset, item in enumerate(items, start=1):
        note = f"@ {item.quantity_per_unit} pcs" if item.quantity_per_unit else ""
        values = (
            str(offset),
            item.sku or "-",
            item.item_name[:44],
            str(item.quantity),
            item.unit_raw,
            note,
        )
        for (x, _), value in zip(columns, values, strict=True):
            pdf.drawString(x, y, value)

        if spec.layout == "classic":
            pdf.setLineWidth(0.2)
            pdf.setStrokeGray(0.7)
            pdf.line(MARGIN, y - 2 * mm, PAGE_WIDTH - MARGIN, y - 2 * mm)
            pdf.setStrokeGray(0)
        y -= row_height

    if spec.layout == "boxed":
        pdf.setLineWidth(0.6)
        pdf.rect(MARGIN, y + 4.5 * mm, PAGE_WIDTH - 2 * MARGIN, header_y - y - 2 * mm)

    return y


def _draw_footer(pdf: canvas.Canvas, spec: DocumentSpec, y: float) -> None:
    y = min(y - 8 * mm, MARGIN + 45 * mm)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(MARGIN + 2 * mm, y, f"Kendaraan: {spec.vehicle}   Sopir: {spec.driver}")
    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(MARGIN + 2 * mm, y - 4 * mm, spec.footer_note)

    left_label, right_label = spec.signatures
    sign_y = MARGIN + 26 * mm
    pdf.setFont("Helvetica", 8)
    pdf.drawString(MARGIN + 6 * mm, sign_y, left_label)
    pdf.drawRightString(PAGE_WIDTH - MARGIN - 6 * mm, sign_y, right_label)
    pdf.setLineWidth(0.4)
    pdf.line(MARGIN + 4 * mm, MARGIN + 8 * mm, MARGIN + 46 * mm, MARGIN + 8 * mm)
    right_start = PAGE_WIDTH - MARGIN - 46 * mm
    pdf.line(right_start, MARGIN + 8 * mm, PAGE_WIDTH - MARGIN - 4 * mm, MARGIN + 8 * mm)


def render_pdf(spec: DocumentSpec, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(destination), pagesize=A4)
    pdf.setTitle(spec.truth.document_number)

    for page in range(1, spec.truth.page_count + 1):
        page_items = [item for item in spec.truth.items if item.source_page == page]
        y = _draw_header(pdf, spec, page)
        y = _draw_table(pdf, spec, page_items, y)
        _draw_footer(pdf, spec, y)
        pdf.showPage()

    pdf.save()
    return destination
