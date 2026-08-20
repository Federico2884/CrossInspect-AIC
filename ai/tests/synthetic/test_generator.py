"""Test generator sintetis.

Fokusnya bukan estetika PDF, melainkan hal yang bisa merusak evaluasi step 4:
determinisme, dan ground truth yang benar-benar cocok dengan isi dokumen.
"""

import json

import pytest

from app.modules.document.schemas import Item, UnitNormalized
from scripts.synthetic import vocab
from scripts.synthetic.document import LAYOUTS, build_spec, format_date

pytest.importorskip("reportlab", reason="reportlab hanya ada di requirements-dev.txt")

from scripts.generate_synthetic import generate, parse_args  # noqa: E402
from scripts.synthetic.render import render_pdf  # noqa: E402


def test_same_seed_produces_identical_ground_truth():
    first = build_spec(seed=7, doc_id="sj_0001").truth
    second = build_spec(seed=7, doc_id="sj_0001").truth
    assert first.model_dump_json() == second.model_dump_json()


def test_different_seeds_produce_different_documents():
    numbers = {build_spec(seed=s, doc_id=f"d{s}").truth.document_number for s in range(25)}
    assert len(numbers) > 20  # sedikit tabrakan wajar, keseragaman tidak


def test_ground_truth_items_satisfy_the_contract():
    for seed in range(30):
        for item in build_spec(seed=seed, doc_id=f"d{seed}").truth.items:
            assert isinstance(item, Item)
            assert item.quantity >= 0
            assert item.unit_raw in vocab.UNIT_MAP
            assert item.unit_normalized is vocab.UNIT_MAP[item.unit_raw]


def test_total_pieces_matches_quantity_arithmetic():
    for seed in range(30):
        for item in build_spec(seed=seed, doc_id=f"d{seed}").truth.items:
            if item.quantity_per_unit is None:
                assert item.total_pieces is None
            else:
                assert item.total_pieces == item.quantity * item.quantity_per_unit


def test_source_page_never_exceeds_page_count():
    for seed in range(50):
        truth = build_spec(seed=seed, doc_id=f"d{seed}").truth
        assert truth.page_count >= 1
        for item in truth.items:
            assert 1 <= item.source_page <= truth.page_count


def test_unknown_units_are_generated_but_keep_their_raw_text():
    raws = {
        item.unit_raw
        for seed in range(120)
        for item in build_spec(seed=seed, doc_id=f"d{seed}").truth.items
        if item.unit_normalized is UnitNormalized.UNKNOWN
    }
    # Satuan di luar enum harus benar-benar muncul di dataset, bukan teori.
    assert raws & {"Ball", "Slop", "Renceng"}


def test_all_layouts_are_reachable():
    layouts = {build_spec(seed=seed, doc_id=f"d{seed}").layout for seed in range(60)}
    assert layouts == set(LAYOUTS)


def test_format_date_styles():
    from datetime import date

    when = date(2026, 8, 15)
    assert format_date(when, "iso") == "15-08-2026"
    assert format_date(when, "slash") == "15/08/2026"
    assert format_date(when, "long") == "15 Agustus 2026"


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_rendered_pdf_is_valid_and_has_expected_page_count(tmp_path, seed):
    spec = build_spec(seed=seed, doc_id=f"sj_{seed:04d}")
    path = render_pdf(spec, tmp_path / f"{spec.truth.doc_id}.pdf")

    content = path.read_bytes()
    assert content.startswith(b"%PDF-")

    fitz = pytest.importorskip("fitz")
    with fitz.open(path) as document:
        assert document.page_count == spec.truth.page_count


def test_rendered_pdf_contains_the_ground_truth_values(tmp_path):
    """Kalau teks ini tidak ada di PDF, label evaluasi bohong."""
    fitz = pytest.importorskip("fitz")
    spec = build_spec(seed=11, doc_id="sj_0011")
    path = render_pdf(spec, tmp_path / "doc.pdf")

    with fitz.open(path) as document:
        pages = [page.get_text() for page in document]

    assert spec.truth.document_number in pages[0]
    assert (spec.truth.recipient or "") in pages[0]
    for item in spec.truth.items:
        page_text = pages[item.source_page - 1]
        assert item.item_name[:44] in page_text
        assert str(item.quantity) in page_text


def test_generate_writes_manifest_truth_and_pdfs(tmp_path):
    entries = generate(count=3, seed=5, out=tmp_path, degrade_ratio=0.0)

    assert len(entries) == 3
    manifest_lines = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(manifest_lines) == 3

    for entry in entries:
        assert (tmp_path / entry["pdf"]).exists()
        truth = json.loads((tmp_path / entry["truth"]).read_text(encoding="utf-8"))
        assert truth["doc_id"] == entry["doc_id"]
        assert len(truth["items"]) == entry["items"]
        assert entry["images"] == []  # degrade_ratio 0.0


def test_generate_is_reproducible(tmp_path):
    first = generate(count=2, seed=99, out=tmp_path / "a", degrade_ratio=0.0)
    second = generate(count=2, seed=99, out=tmp_path / "b", degrade_ratio=0.0)

    for left, right in zip(first, second, strict=True):
        left_truth = (tmp_path / "a" / left["truth"]).read_text(encoding="utf-8")
        right_truth = (tmp_path / "b" / right["truth"]).read_text(encoding="utf-8")
        assert left_truth == right_truth


def test_cli_defaults_match_the_documented_workflow():
    args = parse_args([])
    assert (args.count, args.seed, args.prefix) == (200, 42, "sj")
    assert str(args.out).replace("\\", "/") == "data/synthetic"


def test_pick_severity_round_robin_keeps_levels_balanced():
    from scripts.generate_synthetic import SEVERITIES, pick_severity

    picks = [pick_severity(i, "mixed") for i in range(30)]
    assert {picks.count(level) for level in SEVERITIES} == {10}


def test_pick_severity_respects_a_forced_level():
    from scripts.generate_synthetic import pick_severity

    assert {pick_severity(i, "heavy") for i in range(9)} == {"heavy"}


def test_degrade_rejects_an_unknown_severity():
    import numpy as np

    from scripts.synthetic.degrade import degrade

    with pytest.raises(ValueError, match="severity"):
        degrade(np.zeros((8, 8, 3), dtype=np.uint8), seed=1, severity="apocalyptic")


def test_cli_severity_defaults_to_mixed():
    assert parse_args([]).severity == "mixed"
    assert parse_args(["--severity", "heavy"]).severity == "heavy"


def test_manifest_records_severity_only_for_degraded_documents(tmp_path):
    entries = generate(count=2, seed=3, out=tmp_path, degrade_ratio=0.0)
    assert [entry["severity"] for entry in entries] == [None, None]
