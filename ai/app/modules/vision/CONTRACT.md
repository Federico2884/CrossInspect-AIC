# Kontrak API Physical Inspection

Kontrak resmi untuk **Modul 2 (Physical Inspection)** CrossInspect AI.
Ditegakkan oleh model Pydantic di [`schemas.py`](schemas.py); kalau dokumen ini dan model
tersebut sampai berbeda, modelnya yang benar dan dokumen ini yang salah.

Dokumen ini hanya memuat yang **khas Modul 2**. Aturan yang berlaku di semua modul — batas
unggahan, amplop error, arti `meta`, pembedaan warning dari error — ada di
[`CONTRACT.md`](../../../CONTRACT.md) induk, dan sebaiknya dibaca lebih dulu.

Pembaca: siapa pun yang menulis klien Laravel atau cross-check engine. Kontrak ini
sudah bisa dipakai hari ini — endpoint-nya hidup, dilayani model YOLO asli bila
stack ML terpasang, dan mock deterministik bila tidak.

---

## Endpoint

```
POST http://ai:8000/vision/inspect
Content-Type: multipart/form-data
```

Dari host (untuk debugging): `http://localhost:8001/vision/inspect`.

| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `file` | file | ya | **PNG, JPEG, atau WebP.** Maksimal 20 MB. PDF **ditolak**. |
| `scenario` | string | tidak | **Khusus mock.** Memaksa fixture tertentu — lihat [Skenario](#skenario). |

Perhatikan bedanya dari Modul 1: WebP diterima di sini, PDF tidak.

### Engine mana yang sedang melayani

```
GET http://ai:8000/vision/engine
```

```json
{
  "configured": "auto", "active": "yolo", "yolo_available": true,
  "model_path": "/srv/ai/models/inspection.pt", "model_present": true,
  "conf_threshold": 0.4
}
```

Terpisah dari `/health` karena health dipakai HEALTHCHECK tiap 15 detik dan harus
tetap murah, sedangkan ini menyentuh filesystem.

---

## Respons — 200

```json
{
  "detected_count": 12,
  "class_counts": { "cardboard": 12 },
  "detections": [
    { "class_name": "cardboard", "confidence": 0.8642,
      "bbox": { "x1": 0.0468, "y1": 0.0833, "x2": 0.25, "y2": 0.3333 } }
  ],
  "count_confidence": { "mean_detection": 0.7421, "min_detection": 0.4133, "overall": 0.7421 },
  "defect": { "status": "unavailable", "findings": [] },
  "warnings": [
    { "code": "DEFECT_CHECK_UNAVAILABLE", "message": "…", "severity": "info", "detection_index": null }
  ],
  "meta": {
    "engine": "yolo", "device": "cpu", "processing_ms": 121,
    "model": "inspection.pt", "conf_threshold": 0.4,
    "image_width": 1280, "image_height": 960,
    "scenario": null, "debug": { "occlusion_ratio": 0.0, "classes": { "0": "cardboard" } }
  }
}
```

### Field

| Field | Tipe | Keterangan |
|---|---|---|
| `detected_count` | int ≥ 0 | **Angka utama.** Jumlah kemasan terluar yang terlihat. |
| `class_counts` | object | Jumlah per nama kelas. Satu entri selama model masih satu kelas. |
| `detections[]` | array | Satu entri per objek. Panjangnya **selalu** sama dengan `detected_count`. |
| `count_confidence` | object | `mean_detection`, `min_detection`, `overall`. Semuanya 0.0–1.0. |
| `defect` | object | `status` + `findings[]`. Lihat [Integritas fisik](#integritas-fisik). |
| `warnings[]` | array | Masalah kualitas inspeksi. **Bukan** error. |
| `meta` | object | Field umum di [kontrak induk](../../../CONTRACT.md#meta), ditambah `model`, `conf_threshold`, `image_width`, `image_height`. |

### Field deteksi

| Field | Tipe | Keterangan |
|---|---|---|
| `class_name` | string | Nama kelas apa adanya dari bobot, tidak dipetakan ulang. |
| `confidence` | float 0.0–1.0 | |
| `bbox` | object | `x1`,`y1`,`x2`,`y2` — **ternormalisasi 0.0–1.0**, bukan piksel. |

> **Catatan bbox.** Dinormalisasi supaya overlay bisa digambar di ukuran tampilan
> berapa pun tanpa menghitung ulang skala. Untuk kembali ke piksel:
> `x_px = x1 * meta.image_width`.

> **Catatan cross-check.** Untuk `10 karton @ 12 pcs` di Surat Jalan, bandingkan
> `detected_count` dengan **`quantity` (10)** dari Modul 1 — bukan `total_pieces`
> (120). Kamera hanya melihat kemasan terluar; isi kardus yang tersegel tidak
> terlihat sama sekali.

> **Catatan satuan.** Tidak semua baris bisa diverifikasi visual. Baris dengan
> `unit_normalized` bernilai `kg` adalah berat, bukan cacah — cross-check engine
> harus punya jalur "tidak dapat diverifikasi", bukan memaksakan perbandingan
> lalu melaporkan selisih palsu.

---

## Integritas fisik

Parameter ke-3 di dokumen konsep (deteksi penyok/robek/basah) **belum tersedia**:
model yang ada dilatih satu kelas untuk menghitung kemasan, tanpa kelas kerusakan.

`defect.status` karenanya selalu `"unavailable"` untuk sekarang, dan setiap
respons membawa warning `DEFECT_CHECK_UNAVAILABLE` ber-severity `info`.

| `status` | Arti |
|---|---|
| `unavailable` | Pemeriksaan tidak dijalankan. `findings` dijamin kosong. |
| `clean` | Diperiksa, tidak ditemukan kerusakan. |
| `defect_suspected` | Ditemukan dugaan kerusakan; `findings` berisi minimal satu entri. |

Schema **menolak** `findings` yang tidak kosong saat status `unavailable`. Itu
disengaja: tidak boleh ada yang mengarang temuan cacat selama modelnya belum ada.

UI sebaiknya menampilkan "belum diperiksa", bukan "kemasan aman" — dua hal yang
sangat berbeda bagi petugas gudang.

---

## Warning

Prinsip warning-vs-error ada di [kontrak induk](../../../CONTRACT.md#warning-vs-error).
Kode berikut khas Modul 2:

| Code | Severity | Arti |
|---|---|---|
| `DEFECT_CHECK_UNAVAILABLE` | info | Selalu ada selama model cacat belum tersedia. |
| `NO_OBJECT_DETECTED` | error | Tidak ada kemasan terdeteksi. `detected_count` = 0. |
| `POSSIBLE_OCCLUSION` | warning | Kotak saling bertindihan; hitungan cenderung **lebih rendah** dari kenyataan. |
| `COUNT_UNRELIABLE` | warning | Confidence rata-rata rendah; minta konfirmasi petugas. |
| `LOW_CONFIDENCE_DETECTION` | warning | Satu objek lemah; `detection_index` menunjuk ke `detections[i]`. |
| `IMAGE_LOW_RESOLUTION` | warning | Sisi terpendek di bawah ambang; akurasi menurun. |

## Error

Di luar [kode umum](../../../CONTRACT.md#amplop-error), Modul 2 menambah dua kode.
`UNSUPPORTED_FILE_TYPE` di sini berarti berkasnya bukan PNG, JPEG, maupun WebP.

| HTTP | Code | Penyebab |
|---|---|---|
| 422 | `UNREADABLE_IMAGE` | Magic bytes benar tetapi isinya tidak bisa didekode. |
| 503 | `VISION_ENGINE_UNAVAILABLE` | `AI_VISION_ENGINE=yolo` dipaksa tetapi ultralytics/bobot tidak ada. |

---

## Skenario

Tujuh fixture mock. Cara kerjanya ada di [kontrak induk](../../../CONTRACT.md#skenario-khusus-mock).

| `scenario` | Yang diuji |
|---|---|
| `clean_stack` | Jalur normal, 12 kardus, confidence tinggi |
| `partial_occlusion` | Kotak bertindihan, `overall` turun di bawah `mean_detection` |
| `single_item` | Satu objek |
| `crowded` | 30 objek padat + peringatan undercount |
| `low_confidence` | `COUNT_UNRELIABLE` + `LOW_CONFIDENCE_DETECTION` ber-`detection_index` |
| `empty` | 0 deteksi, warning ber-severity `error`, tetap 200 |
| `low_resolution` | `IMAGE_LOW_RESOLUTION` |

Bangun klien Laravel dengan `partial_occlusion` dan `empty` lebih dulu — jalur
normal justru yang paling mudah; dua skenario itulah yang benar-benar menguji
logika cross-check.

```bash
curl -F "file=@stack.jpg" -F "scenario=partial_occlusion" http://localhost:8001/vision/inspect
```

---

## Batasan yang diketahui

Disebutkan terbuka karena memengaruhi cara cross-check engine menafsirkan angkanya.

**Hitungan adalah batas bawah, bukan angka pasti.** Bobot saat ini (YOLOv12n,
30 epoch) mencatat precision 0.701, recall 0.563, mAP@50 0.640, dan mAP@50-95
0.425 pada set validasi berisi 453 gambar dan 1.424 instance. Artinya
sebagian kemasan memang terlewat, terutama pada tumpukan bertindihan. Karena itu
`POSSIBLE_OCCLUSION` ada, dan karena itu `count_confidence.overall` diturunkan
saat occlusion terdeteksi. Model akan dilatih ulang; angka-angka ini akan berubah,
kontraknya tidak.

**Hanya kemasan terluar yang terlihat.** Barang di baris belakang tumpukan tidak
tertangkap kamera *line-of-sight*. Ini batasan metode, bukan bug — dan menjadi
dasar roadmap multi-angle stitching / IoT overhead camera di proposal.

**Occlusion ratio adalah proksi.** Dihitung dari tumpang tindih bbox di bidang
gambar (IoU > `AI_VISION_OCCLUSION_IOU`), bukan pengukuran kedalaman. Ia cukup
untuk menaikkan bendera, tidak cukup untuk mengoreksi hitungan.

---

## Jaminan stabilitas

Training ulang mengganti bobot di balik antarmuka yang sama
([`engines/base.py`](engines/base.py)), dan **bentuk respons tidak berubah** — field, tipe,
dan aturan validasinya sama persis. Jaminan umum soal `meta` ada di
[kontrak induk](../../../CONTRACT.md#yang-dijamin-stabil).

Yang khas Modul 2 saat bobot ditukar:

- `meta.engine` tetap `"yolo"`; `meta.model` menunjuk nama berkas bobot yang dipakai.
- `class_counts` bisa bertambah kunci bila model baru punya kelas tambahan —
  kontrak sudah menampungnya sejak awal, jadi ini **bukan** perubahan breaking.
- `defect.status` berpindah dari `unavailable` begitu model kerusakan tersedia.

Normalisasi bbox dan aturan `detected_count == len(detections)` adalah kontrak, bukan detail
implementasi.

---

## Konfigurasi

Semua lewat environment, prefix `AI_`. Tidak ada ambang yang di-hardcode, supaya
bobot hasil training ulang bisa dikalibrasi tanpa menyentuh kode.

| Env | Default | Keterangan |
|---|---|---|
| `AI_VISION_ENGINE` | `auto` | `auto` / `yolo` / `mock`. `auto` jatuh ke mock bila torch tak ada. |
| `AI_VISION_MODEL_PATH` | `models/inspection.pt` | Relatif terhadap `/srv/ai`. |
| `AI_VISION_CONF_THRESHOLD` | `0.40` | Sama dengan `conf` di notebook training. |
| `AI_VISION_IMGSZ` | `640` | Harus sama dengan `imgsz` saat training. |
| `AI_VISION_MIN_RESOLUTION` | `640` | Di bawah ini memicu `IMAGE_LOW_RESOLUTION`. |
| `AI_VISION_OCCLUSION_IOU` | `0.15` | IoU minimum agar dua kotak dihitung bertindihan. |
| `AI_VISION_OCCLUSION_RATIO_ALERT` | `0.30` | Porsi kotak bertindihan yang memicu warning. |
| `AI_VISION_UNRELIABLE_BELOW` | `0.55` | Mean confidence di bawah ini memicu `COUNT_UNRELIABLE`. |
| `AI_VISION_LOW_CONFIDENCE_MARGIN` | `0.10` | Selisih di atas threshold yang masih dianggap lemah. |

Deteksi asli hanya berjalan di image yang memuat `requirements-ml.txt`:

```bash
AI_DOCKERFILE=Dockerfile.ml docker compose up --build
```

Dengan `Dockerfile` bawaan (slim, tanpa torch), `/vision/inspect` tetap menjawab —
tetapi dilayani mock. Periksa `meta.engine` atau `GET /vision/engine` untuk tahu
mana yang sedang aktif.
