"""CLI evaluasi Modul 1 terhadap dataset berlabel step 3.

Contoh:
    python scripts/evaluate.py --source pdf                    # cepat, engine mock
    python scripts/evaluate.py --sample 12 --seed 42
    python scripts/evaluate.py --doc-id sj_0030                # bedah satu dokumen

Hasil per panggilan ditulis ke JSONL **begitu selesai**, bukan di akhir. Dengan
inference CPU yang memakan menit per halaman, satu run penuh berjam-jam; run
yang terputus di tengah harus tetap menyisakan hasil dan bisa dilanjutkan.
Menjalankan ulang perintah yang sama akan melewati yang sudah terukur.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time
from collections import defaultdict
from typing import Any

# Jalankan sebagai skrip: pastikan root paket 'ai/' ada di sys.path.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.modules.document.engines.base import DocumentPayload  # noqa: E402
from app.modules.document.service import get_engine  # noqa: E402
from scripts.evaluation.matching import DEFAULT_THRESHOLD  # noqa: E402
from scripts.evaluation.metrics import DocumentScore, score_document  # noqa: E402
from scripts.evaluation.report import render  # noqa: E402
from scripts.synthetic.document import GroundTruth  # noqa: E402

DEFAULT_DATA = pathlib.Path("data/synthetic")
DEFAULT_OUT = pathlib.Path("data/eval")
REPORT_PATH = pathlib.Path("EVALUATION.md")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluasi engine Modul 1.")
    parser.add_argument("--data", type=pathlib.Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--sample", type=int, default=0, help="0 = seluruh dataset")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--doc-id", action="append", default=[], dest="doc_ids")
    parser.add_argument("--source", choices=("pdf", "image", "both"), default="both")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="ukur ulang semuanya, abaikan hasil yang sudah ada",
    )
    parser.add_argument("--report-only", action="store_true", help="susun laporan dari JSONL")
    return parser.parse_args(argv)


def load_manifest(data: pathlib.Path) -> list[dict[str, Any]]:
    lines = (data / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def stratify(entries: list[dict[str, Any]], sample: int, seed: int) -> list[dict[str, Any]]:
    """Ambil sampel yang menyebar rata di severity, layout, dan jumlah halaman.

    Sampel acak biasa gampang kebetulan berisi dokumen mudah semua, dan dengan
    biaya beberapa menit per dokumen, tiap pilihan harus berarti.
    """
    if sample <= 0 or sample >= len(entries):
        return entries

    buckets: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        buckets[(entry.get("severity"), entry.get("layout"), entry.get("pages"))].append(entry)

    rng = random.Random(seed)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    # Kunci bucket memuat None (severity dokumen bersih) bercampur string, dan
    # keduanya tidak bisa dibandingkan langsung. Disamakan jadi string dulu
    # supaya urutannya tetap deterministik tanpa melempar.
    def sort_key(key: tuple) -> tuple:
        return tuple("" if part is None else str(part) for part in key)

    order = sorted(buckets, key=sort_key)
    picked: list[dict[str, Any]] = []
    while len(picked) < sample:
        progressed = False
        for key in order:
            if buckets[key]:
                picked.append(buckets[key].pop())
                progressed = True
                if len(picked) == sample:
                    break
        if not progressed:
            break

    return sorted(picked, key=lambda e: e["doc_id"])


def already_done(path: pathlib.Path) -> set[tuple[str, str, int | None]]:
    if not path.exists():
        return set()
    done: set[tuple[str, str, int | None]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # baris separuh tertulis akibat run yang dibunuh
        done.add((row["doc_id"], row["source"], row.get("page")))
    return done


def read_scores(path: pathlib.Path) -> list[DocumentScore]:
    scores: list[DocumentScore] = []
    if not path.exists():
        return scores
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        row["confidence_pairs"] = [tuple(pair) for pair in row.get("confidence_pairs", [])]
        scores.append(DocumentScore(**row))
    return scores


def jobs_for(entry: dict[str, Any], source: str) -> list[tuple[str, int | None, pathlib.Path]]:
    """Panggilan engine yang perlu dilakukan untuk satu dokumen.

    PDF dikirim utuh sekali. Foto tidak bisa begitu: tiap halaman adalah berkas
    gambar tersendiri, sama seperti petugas gudang yang memotret halaman satu
    per satu, jadi tiap halaman jadi panggilan sendiri.
    """
    jobs: list[tuple[str, int | None, pathlib.Path]] = []
    if source in ("pdf", "both"):
        jobs.append(("pdf", None, pathlib.Path(entry["pdf"])))
    if source in ("image", "both"):
        for index, image in enumerate(entry.get("images") or [], start=1):
            jobs.append(("image", index, pathlib.Path(image)))
    return jobs


def media_type_for(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    return "image/png" if suffix == ".png" else "image/jpeg"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = args.data
    args.out.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    engine_name = getattr(engine, "name", "unknown")
    slug = engine_name.replace("/", "_")
    results_path = args.out / f"results-{slug}.jsonl"

    if not args.report_only:
        entries = load_manifest(data)
        if args.doc_ids:
            wanted = set(args.doc_ids)
            chosen = [e for e in entries if e["doc_id"] in wanted]
            missing = wanted - {e["doc_id"] for e in chosen}
            if missing:
                print(f"doc_id tidak ada di manifest: {sorted(missing)}", file=sys.stderr)
            if args.sample:
                chosen += stratify(
                    [e for e in entries if e["doc_id"] not in wanted], args.sample, args.seed
                )
        else:
            chosen = stratify(entries, args.sample, args.seed)

        done = set() if args.no_resume else already_done(results_path)
        mode = "w" if args.no_resume else "a"

        planned = [(entry, job) for entry in chosen for job in jobs_for(entry, args.source)]
        todo = [(e, j) for e, j in planned if (e["doc_id"], j[0], j[1]) not in done]
        print(
            f"engine={engine_name} · {len(chosen)} dokumen · {len(planned)} panggilan "
            f"· {len(planned) - len(todo)} sudah ada · {len(todo)} akan dijalankan",
            flush=True,
        )

        with results_path.open(mode, encoding="utf-8") as sink:
            for position, (entry, (source, page, relative)) in enumerate(todo, start=1):
                truth = GroundTruth.model_validate_json(
                    (data / entry["truth"]).read_text(encoding="utf-8")
                )
                truth_items = (
                    list(truth.items)
                    if source == "pdf"
                    else [i for i in truth.items if i.source_page == page]
                )

                payload = DocumentPayload(
                    content=(data / relative).read_bytes(),
                    media_type=media_type_for(relative),
                    filename=relative.name,
                )

                started = time.perf_counter()
                response = engine.parse(payload)
                elapsed = time.perf_counter() - started

                score = score_document(
                    doc_id=entry["doc_id"],
                    source=source,
                    page=page,
                    severity=entry.get("severity") if source == "image" else None,
                    layout=entry.get("layout"),
                    engine=engine_name,
                    latency_s=elapsed,
                    truth=truth,
                    response=response,
                    truth_items=truth_items,
                    score_header=(source == "pdf" or page == 1),
                    score_page_count=(source == "pdf"),
                    threshold=args.threshold,
                )

                # Ditulis dan di-flush per panggilan: run berjam-jam yang
                # terputus tidak boleh kehilangan apa pun.
                sink.write(json.dumps(score.to_json(), ensure_ascii=False) + "\n")
                sink.flush()

                print(
                    f"[{position}/{len(todo)}] {entry['doc_id']} {source}"
                    f"{f' hal.{page}' if page else ''} · {elapsed:6.1f}s · "
                    f"baris {score.rows_matched}/{score.rows_truth} · "
                    f"jumlah benar {score.quantity_ok}/{max(score.rows_matched, 1)}",
                    flush=True,
                )

    scores = read_scores(results_path)
    if not scores:
        print("belum ada hasil untuk dilaporkan", file=sys.stderr)
        return 1

    REPORT_PATH.write_text(render(scores, engine_name, args.threshold), encoding="utf-8")
    print(f"\nlaporan: {REPORT_PATH} ({len(scores)} panggilan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
