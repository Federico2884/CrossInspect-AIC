"""Test pemilihan dokumen dan perencanaan panggilan.

Bagian ini sempat lolos dari validasi: run percobaan memakai seluruh dataset
tanpa ``--sample``, sehingga jalur stratifikasi tidak pernah dieksekusi dan
baru meledak saat run sungguhan. Sekarang diuji langsung.
"""

import pathlib

from scripts.evaluate import jobs_for, media_type_for, stratify


def entry(doc_id, severity=None, layout="classic", pages=1, images=None):
    return {
        "doc_id": doc_id,
        "severity": severity,
        "layout": layout,
        "pages": pages,
        "pdf": f"pdf/{doc_id}.pdf",
        "truth": f"truth/{doc_id}.json",
        "images": images or [],
    }


def mixed_entries():
    """Campuran dokumen bersih (severity None) dan terdegradasi (severity str)."""
    return [
        entry("sj_0000"),
        entry("sj_0001", severity="light", layout="minimal", pages=2),
        entry("sj_0002", severity="heavy", layout="boxed"),
        entry("sj_0003"),
        entry("sj_0004", severity="medium", pages=3),
        entry("sj_0005", layout="minimal"),
    ]


def test_none_severity_mixed_with_strings_does_not_raise():
    """Bug yang menghentikan run pertama: None dan str dibandingkan langsung."""
    picked = stratify(mixed_entries(), sample=3, seed=42)

    assert len(picked) == 3


def test_sampling_is_deterministic_for_a_given_seed():
    first = stratify(mixed_entries(), sample=4, seed=7)
    second = stratify(mixed_entries(), sample=4, seed=7)

    assert [e["doc_id"] for e in first] == [e["doc_id"] for e in second]


def test_different_seeds_can_pick_differently():
    entries = [entry(f"sj_{i:04d}", severity="light") for i in range(20)]
    a = {e["doc_id"] for e in stratify(entries, sample=5, seed=1)}
    b = {e["doc_id"] for e in stratify(entries, sample=5, seed=2)}

    assert a != b


def test_sample_spreads_across_severities_rather_than_clustering():
    """Sampel yang kebetulan berisi dokumen mudah semua tidak berguna."""
    entries = (
        [entry(f"clean_{i}", severity=None) for i in range(10)]
        + [entry(f"light_{i}", severity="light") for i in range(10)]
        + [entry(f"heavy_{i}", severity="heavy") for i in range(10)]
    )
    picked = stratify(entries, sample=6, seed=42)
    severities = {e["severity"] for e in picked}

    assert len(severities) == 3


def test_zero_or_oversized_sample_returns_everything():
    entries = mixed_entries()

    assert stratify(entries, sample=0, seed=1) == entries
    assert stratify(entries, sample=99, seed=1) == entries


def test_picked_documents_are_unique():
    entries = [entry(f"sj_{i:04d}", severity="light") for i in range(10)]
    picked = stratify(entries, sample=6, seed=3)

    assert len({e["doc_id"] for e in picked}) == 6


def test_pdf_source_is_one_call_per_document():
    jobs = jobs_for(entry("sj_0001", pages=3), "pdf")

    assert len(jobs) == 1
    assert jobs[0][0] == "pdf"
    assert jobs[0][1] is None  # tanpa nomor halaman: dokumen dikirim utuh


def test_image_source_is_one_call_per_page():
    """Foto tidak bisa dikirim sekaligus — tiap halaman berkas tersendiri."""
    jobs = jobs_for(
        entry("sj_0001", pages=2, images=["images/sj_0001_p1.jpg", "images/sj_0001_p2.jpg"]),
        "image",
    )

    assert [job[1] for job in jobs] == [1, 2]
    assert all(job[0] == "image" for job in jobs)


def test_both_covers_pdf_and_every_page_image():
    jobs = jobs_for(
        entry("sj_0001", pages=2, images=["images/a.jpg", "images/b.jpg"]),
        "both",
    )

    assert [job[0] for job in jobs] == ["pdf", "image", "image"]


def test_clean_document_has_no_image_jobs():
    assert jobs_for(entry("sj_0000"), "image") == []
    assert len(jobs_for(entry("sj_0000"), "both")) == 1


def test_media_type_follows_the_extension():
    assert media_type_for(pathlib.Path("a/b.pdf")) == "application/pdf"
    assert media_type_for(pathlib.Path("a/b.PNG")) == "image/png"
    assert media_type_for(pathlib.Path("a/b.jpg")) == "image/jpeg"
    assert media_type_for(pathlib.Path("a/b.jpeg")) == "image/jpeg"
