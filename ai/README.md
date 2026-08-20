# CrossInspect AI — Service

Service FastAPI untuk **Modul 1 (Document Parsing)**: menerima Surat Jalan atau Invoice berupa
PDF/foto, lalu mengembalikan isinya sebagai JSON terstruktur.

Bentuk response-nya dikunci oleh [`CONTRACT.md`](CONTRACT.md). Kalau dokumen itu dan model
Pydantic di `app/modules/document/schemas.py` berbeda, modelnya yang benar.

## Tiga image, tiga keperluan

| Image | Isi | Dipakai untuk |
|---|---|---|
| `Dockerfile` | FastAPI + PyMuPDF + Pillow | Runtime harian: engine mock dan rendering. Ringan. |
| `Dockerfile.dev` | + pytest, ruff, ReportLab, Augraphy | Test dan generator dataset. **Tidak pernah dideploy.** |
| `Dockerfile.ml` | + torch/transformers CPU | Inference Qwen2-VL sungguhan. |

Image runtime memang **tidak bisa** menjalankan test-nya sendiri, dan itu disengaja:
`requirements-dev.txt` di-exclude dari build context-nya, sedangkan Augraphy menarik
`opencv-python` versi penuh yang butuh pustaka X11. Keduanya tidak layak ikut ke image yang
dikirim.

## Menjalankan

Service (image slim, engine mock):

```bash
docker compose up -d ai
```

Test dan lint — profil `test` supaya `docker compose up` biasa tidak ikut menjalankannya:

```bash
docker compose --profile test run --rm ai-test python -m pytest -q
```

```bash
docker compose --profile test run --rm ai-test ruff check .
```

Generator dataset evaluasi ada di [`scripts/README.md`](scripts/README.md).

## Mengukur akurasi

`scripts/evaluate.py` menilai engine terhadap dataset berlabel step 3 dan menulis
[`EVALUATION.md`](EVALUATION.md). Cepat dan gratis dengan engine mock — berguna untuk memastikan
harness-nya sendiri jalan, walau skornya jelas jelek karena mock memang tidak membaca dokumen:

```bash
docker compose --profile test run --rm ai-test python scripts/evaluate.py --source pdf
```

Dengan engine asli, `scripts/` dan `data/` tidak ikut ke build context image ML, jadi direktori
`ai/` perlu di-bind mount:

```bash
AI_DOCKERFILE=Dockerfile.ml docker compose run --rm --no-deps --user root -v "${PWD}/ai:/srv/ai" -e AI_ENGINE=qwen2vl ai python -u scripts/evaluate.py --sample 12 --seed 42
```

**`--user root` itu wajib, bukan hiasan.** Image test berjalan sebagai root sedangkan
`Dockerfile.ml` turun ke `aiuser`; berkas hasil run mock jadi milik root, dan container ML tidak
bisa menulis ke sana. Tanpa flag itu hasilnya `PermissionError` setelah model selesai dimuat —
gagal di menit kesekian, bukan di detik pertama.

Hasil per panggilan ditulis ke `data/eval/results-{engine}.jsonl` **saat itu juga**, dan
menjalankan ulang perintah yang sama akan melanjutkan, bukan mengulang. Run penuh 200 dokumen
memakan 15–20 jam, jadi sifat itu penting.

Hilangkan `--sample` untuk mengukur seluruh dataset.

> Angka **Jumlah halaman** untuk sumber foto pada `EVALUATION.md` yang ada sekarang keliru:
> satu foto memang satu halaman, tetapi saat itu dibandingkan dengan jumlah halaman dokumen
> aslinya. Penilainya sudah diperbaiki; laporannya ikut benar begitu evaluasi dijalankan ulang.

## Memilih engine

| `AI_ENGINE` | Engine | Syarat |
|---|---|---|
| `mock` (default) | 7 fixture deterministik | image slim sudah cukup |
| `qwen2vl` | Qwen2-VL-2B-Instruct | **wajib** `AI_DOCKERFILE=Dockerfile.ml` |

```bash
AI_DOCKERFILE=Dockerfile.ml AI_ENGINE=qwen2vl docker compose up -d ai
```

Default sengaja `mock`: klien Laravel dan sebagian besar pekerjaan kontrak tidak perlu menunggu
inference CPU, dan mock menjawab dalam milidetik. Yang berubah saat engine asli aktif hanyalah
`meta.engine` — bentuk response-nya tetap.

Field `scenario` hanya berlaku untuk mock dan diabaikan oleh engine asli.

## Bobot model

Sekitar 4,4 GB, disimpan di volume `ai-hf-cache` supaya tidak diunduh ulang setiap
`docker compose up`. Unduhan pertama memakan beberapa menit; sesudah cache hangat, memuat model
hanya ~4 detik.

Container tetap mencoba menghubungi `huggingface.co` setiap kali memuat model, dan gagal DNS di
sana menambah jeda percuma padahal bobotnya sudah ada. Setelah unduhan pertama selesai,
`HF_HUB_OFFLINE=1` menghilangkan perjalanan jaringan itu.

## Angka terukur

Qwen2-VL-2B, CPU, 4 thread. Tiga dokumen bertabel 10 baris; angka kedua adalah baris dengan
nama **dan** jumlah yang benar dari 10.

```
                   ~1260 token      ~494 token
  sj_0029 PDF      254 s  10/10     177 s   9/10
  sj_0029 foto     250 s  10/10     176 s   7/10
  sj_0030 PDF      185 s   0/10     186 s   0/10
  sj_0030 foto     168 s   4/10     155 s   0/10
  sj_0043 PDF      200 s  10/10     198 s   9/10
  sj_0043 foto     176 s   2/10     191 s   8/10
```

Dua hal yang perlu dibaca dengan hati-hati:

**Angka akurasi di atas bukan metrik.** Pencocokannya string persis, sampelnya tiga dokumen.
Anggap sebagai indikator kasar sampai evaluasi step 5 mengukurnya dengan benar.

**Memperkecil gambar hampir tidak menghemat waktu.** Hanya `sj_0029` yang jelas lebih cepat;
pada dua dokumen lain selisihnya di bawah satu detik. Sebabnya, yang memakan waktu adalah
menuliskan JSON baris demi baris, bukan melihat gambarnya. Karena itu `qwen_max_pixels`
dibiarkan tinggi — menurunkannya menukar akurasi dengan kecepatan yang sering tidak datang.

## Batasan yang diketahui

- **Dokumen banyak halaman belum realistis lewat request sinkron.** Satu halaman padat ~200
  detik, sedangkan `qwen_max_model_pages` bernilai 10 — artinya satu dokumen bisa menahan
  request lebih dari setengah jam. Perlu keputusan tersendiri: antrean, batas halaman yang
  lebih ketat, atau menerima batas itu secara eksplisit.
- **Dua kejanggalan akurasi belum terjelaskan.** `sj_0030` mendapat 0/10 pada PDF bersih padahal
  JSON-nya valid, dan foto `sj_0043` benar 8/10 nama tetapi hanya 2/10 nama+jumlah — jumlah
  justru field yang paling menentukan untuk cross-check. Keduanya pekerjaan step 5.
- **`engines/qwen.py` belum punya test otomatis.** Logika rapuhnya (ekstraksi JSON, normalisasi
  satuan, perhitungan confidence) sudah diuji lewat `extraction.py` dan `units.py` tanpa torch,
  tetapi orkestrasi per halaman di engine hanya teruji secara manual.
