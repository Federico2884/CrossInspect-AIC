# Generator Surat Jalan Sintetis

Membuat set evaluasi untuk mengukur Qwen2-VL zero-shot di step 4. Tanpa ini, satu-
satunya cara menilai model adalah membaca hasilnya satu per satu.

## Menjalankan

```bash
docker compose --profile test run --rm ai-test \
  python scripts/generate_synthetic.py --count 200 --seed 42
```

| Flag | Default | Keterangan |
|---|---|---|
| `--count` | 200 | Jumlah dokumen |
| `--seed` | 42 | Seed dasar; dokumen ke-N memakai `seed + N` |
| `--out` | `data/synthetic` | Direktori keluaran (gitignored) |
| `--degrade-ratio` | 0.35 | Porsi dokumen yang dirasterisasi + didegradasi |
| `--severity` | `mixed` | `light` / `medium` / `heavy` / `mixed` (bergilir) |
| `--prefix` | `sj` | Awalan `doc_id` |

## Keluaran

```
data/synthetic/
├── pdf/sj_0000.pdf            # dokumen bersih (selalu dibuat)
├── images/sj_0000_p1.jpg      # hasil "foto/scan" 300 DPI (hanya yang didegradasi)
├── truth/sj_0000.json         # ground truth
└── manifest.jsonl             # satu baris per dokumen
```

Semua keluaran di-gitignore. Dataset **tidak** di-commit — cukup seed-nya, karena
seed yang sama menghasilkan dataset yang identik byte-per-byte.

## Alasan desain

**Data dipisah dari penggambaran.** `document.py` membuat `GroundTruth`, `render.py`
menggambarnya. Keduanya memakai objek yang sama, jadi label evaluasi tidak mungkin
melenceng dari isi PDF. Test `test_rendered_pdf_contains_the_ground_truth_values`
menjaga janji ini.

**Paginasi manual, bukan Platypus.** `source_page` di ground truth harus sama persis
dengan halaman tempat barang tercetak. Auto-flow Platypus tidak memberi jaminan itu.

**`items` memakai `Item` dari kontrak** (`app/modules/document/schemas.py`), bukan
struktur baru — supaya evaluasi step 4 membandingkan hal yang benar-benar sebanding
dengan keluaran `/document/parse`.

**Satuan aneh sengaja ada.** `Ball`, `Slop`, `Renceng`, `Zak` muncul di dataset dan
dipetakan ke `unknown`. Kalau set evaluasi hanya berisi `pcs`/`box`, kelemahan normalisasi
tidak akan pernah terlihat.

**Degradasi bertingkat.** `light` (scan kantor), `medium` (foto HP, miring, cahaya
tidak rata), `heavy` (kertas terlipat, fotokopi lusuh). Manifest mencatat tingkatnya
supaya akurasi step 4 bisa dipecah per tingkat — satu angka rata-rata menyembunyikan
di mana model benar-benar gagal.

Batasnya: **teks harus tetap terbaca manusia**. `DirtyDrum`/`DirtyRollers` ditahan
rendah karena pada 300 DPI keduanya menghasilkan pita hitam yang menelan satu baris
tabel; baris yang hilang membuat ground truth-nya jadi label yang tidak adil.
