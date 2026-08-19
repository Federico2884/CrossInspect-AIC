"""CLI generator Surat Jalan sintetis untuk set evaluasi step 4.

Contoh:
    python scripts/generate_synthetic.py --count 200 --seed 42
    python scripts/generate_synthetic.py --count 20 --degrade-ratio 1.0 --severity heavy
    python scripts/generate_synthetic.py --count 50 --out data/eval

Keluaran (semuanya di-gitignore, regenerasi dari seed yang sama):
    <out>/pdf/<doc_id>.pdf                 dokumen bersih
    <out>/images/<doc_id>_p<n>.jpg         hasil "scan"/foto bila didegradasi
    <out>/truth/<doc_id>.json              ground truth per dokumen
    <out>/manifest.jsonl                   satu baris per dokumen
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Jalankan sebagai skrip: pastikan root paket 'ai/' ada di sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.synthetic.document import build_spec  # noqa: E402
from scripts.synthetic.render import render_pdf  # noqa: E402

DEFAULT_OUT = Path("data/synthetic")
SEVERITIES = ("light", "medium", "heavy")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--count", type=int, default=200, help="Jumlah dokumen (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="Seed dasar (default: 42)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Direktori keluaran")
    parser.add_argument(
        "--degrade-ratio",
        type=float,
        default=0.35,
        help="Porsi dokumen yang dirasterisasi + didegradasi (0.0-1.0, default: 0.35)",
    )
    parser.add_argument(
        "--severity",
        choices=(*SEVERITIES, "mixed"),
        default="mixed",
        help="Tingkat degradasi; 'mixed' membagi rata light/medium/heavy (default)",
    )
    parser.add_argument("--prefix", default="sj", help="Awalan doc_id (default: sj)")
    return parser.parse_args(argv)


def pick_severity(index: int, mode: str) -> str:
    """Sebar tingkat degradasi secara bergilir supaya proporsinya pasti.

    Diacak akan membuat jumlah per tingkat tidak sama di dataset kecil, padahal
    evaluasi per-tingkat butuh jumlah sampel yang sebanding.
    """
    if mode != "mixed":
        return mode
    return SEVERITIES[index % len(SEVERITIES)]


def generate(
    count: int,
    seed: int,
    out: Path,
    degrade_ratio: float = 0.0,
    severity: str = "mixed",
    prefix: str = "sj",
) -> list[dict]:
    """Bangun dataset. Kembalikan entri manifest.

    Modul degradasi diimpor malas supaya generator tetap jalan tanpa
    Augraphy/OpenCV saat hanya PDF bersih yang dibutuhkan (mis. di test).
    """
    out.mkdir(parents=True, exist_ok=True)
    degrade_count = round(count * max(0.0, min(1.0, degrade_ratio)))
    entries: list[dict] = []

    for index in range(count):
        doc_id = f"{prefix}_{index:04d}"
        # Seed per dokumen: satu berkas bisa dibuat ulang tanpa dataset lengkap.
        spec = build_spec(seed=seed + index, doc_id=doc_id)

        pdf_path = render_pdf(spec, out / "pdf" / f"{doc_id}.pdf")
        truth_path = out / "truth" / f"{doc_id}.json"
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(spec.truth.model_dump_json(indent=2), encoding="utf-8")

        images: list[str] = []
        page_severity: str | None = None
        if index < degrade_count:
            from scripts.synthetic.degrade import degrade, rasterize, save_image

            page_severity = pick_severity(index, severity)
            for page_number, page in enumerate(rasterize(pdf_path), start=1):
                target = out / "images" / f"{doc_id}_p{page_number}.jpg"
                degraded_page = degrade(
                    page, seed=seed + index + page_number, severity=page_severity
                )
                save_image(degraded_page, target)
                images.append(str(target.relative_to(out)).replace("\\", "/"))

        entries.append(
            {
                "doc_id": doc_id,
                "layout": spec.layout,
                "pages": spec.truth.page_count,
                "items": len(spec.truth.items),
                "pdf": str(pdf_path.relative_to(out)).replace("\\", "/"),
                "truth": str(truth_path.relative_to(out)).replace("\\", "/"),
                "images": images,
                "degraded": bool(images),
                "severity": page_severity,
            }
        )

    manifest = out / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entries


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    entries = generate(
        count=args.count,
        seed=args.seed,
        out=args.out,
        degrade_ratio=args.degrade_ratio,
        severity=args.severity,
        prefix=args.prefix,
    )

    by_severity: dict[str, int] = {}
    for entry in entries:
        if entry["severity"]:
            by_severity[entry["severity"]] = by_severity.get(entry["severity"], 0) + 1

    spread = ", ".join(f"{name}={count}" for name, count in sorted(by_severity.items())) or "-"
    print(
        f"{len(entries)} dokumen -> {args.out}\n"
        f"  halaman    : {sum(e['pages'] for e in entries)}\n"
        f"  baris item : {sum(e['items'] for e in entries)}\n"
        f"  didegradasi: {sum(1 for e in entries if e['degraded'])} ({spread})\n"
        f"  manifest   : {args.out / 'manifest.jsonl'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
