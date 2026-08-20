# Kontrak Service CrossInspect AI

Aturan yang berlaku di **semua** modul: bentuk error, batas unggahan, arti `meta`, dan
pembedaan warning dari error. Yang khas per modul — bentuk response, kode warning, skenario —
ada di kontrak modulnya sendiri.

Ditulis untuk siapa pun yang menulis klien Laravel atau cross-check engine.

## Kontrak per modul

| Modul | Endpoint | Kontrak |
|---|---|---|
| Modul 1 — Document Parsing | `POST /document/parse` | [`app/modules/document/CONTRACT.md`](app/modules/document/CONTRACT.md) |
| Modul 2 — Physical Inspection | `POST /vision/inspect` | [`app/modules/vision/CONTRACT.md`](app/modules/vision/CONTRACT.md) |
| Modul 3 — Cross-Check Engine | `POST /crosscheck` | [`app/modules/crosscheck/CONTRACT.md`](app/modules/crosscheck/CONTRACT.md) |

Modul 3 adalah pengecualian dari beberapa aturan di bawah: ia menerima **JSON**, bukan unggahan
berkas, sehingga batas 20 MB dan aturan magic bytes tidak berlaku baginya.

Tiap kontrak modul ditegakkan oleh `schemas.py` di folder yang sama. Kalau kontrak dan model
Pydantic-nya berbeda, **modelnya yang benar** dan dokumennya yang salah.

Cara menjalankan service, memilih engine, dan angka latensi terukur ada di
[`README.md`](README.md) — bukan di sini.

---

## Unggahan

Semua endpoint menerima `multipart/form-data` dengan field `file`, maksimal **20 MB**.

Format dideteksi dari **magic bytes**, bukan dari nama berkas atau `Content-Type` yang dikirim
klien. Keduanya gampang dipalsukan dan sering salah dari browser, jadi berkas `.txt` yang
diganti namanya jadi `.pdf` akan ditolak. Format apa saja yang diterima berbeda per modul —
lihat kontrak masing-masing.

Dari host, untuk debugging: `http://localhost:8001/…`. Skema interaktif: `http://localhost:8001/docs`.

---

## Warning vs error

Pembedaan ini adalah inti kontrak, bukan detail gaya.

| Keadaan | Balasan |
|---|---|
| Berhasil diproses, tetapi hasilnya meragukan | **200** + `warnings[]` |
| Request gagal | **4xx/5xx** + amplop `error` |

Hasil yang buruk tetap 200 supaya UI bisa menampilkan ketidakpastian — *"barang 3 tidak jelas,
mohon dikonfirmasi"* — alih-alih diam-diam memercayai angka yang salah. Untuk aplikasi gudang
perbedaan ini penting: salah hitung yang tidak disadari lebih berbahaya daripada kegagalan yang
terlihat.

Setiap warning punya `severity`:

| `severity` | Arti |
|---|---|
| `info` | Catatan, tidak menuntut tindakan. |
| `warning` | Hasilnya perlu dikonfirmasi manusia. |
| `error` | Bagian penting gagal, walaupun HTTP-nya tetap 200. |

Cocokkan selalu berdasarkan `code`. Isi `message` ditujukan untuk dibaca manusia, berbahasa
Indonesia, dan kalimatnya bisa berubah sewaktu-waktu.

---

## Amplop error

```json
{ "error": { "code": "FILE_TOO_LARGE", "message": "File exceeds the 20 MB limit.", "detail": "received 21000000 bytes" } }
```

Amplop ini dipakai untuk **semua** kegagalan — bentuk bawaan FastAPI `{"detail": …}` tidak
pernah bocor keluar. Klien cukup menulis satu penangan error, bukan menebak bentuk mana yang
datang.

Kode yang berlaku di semua modul:

| HTTP | Code | Penyebab |
|---|---|---|
| 413 | `FILE_TOO_LARGE` | Lebih dari 20 MB. |
| 422 | `EMPTY_FILE` | Nol byte. |
| 422 | `UNSUPPORTED_FILE_TYPE` | Format tidak didukung menurut magic bytes. Daftar format ada di kontrak modul. |
| 422 | `UNKNOWN_SCENARIO` | `scenario` bukan salah satu yang tersedia di modul tersebut. |
| 422 | `INVALID_REQUEST` | Request tidak valid, misalnya field `file` tidak dikirim. |

Modul boleh menambah kode miliknya sendiri; yang di atas dijamin ada di semua.

---

## `meta`

Setiap response 200 membawa `meta`. Empat field ini ada di semua modul:

| Field | Keterangan |
|---|---|
| `engine` | Engine yang menjawab: `"mock"` atau id model. **Dari sinilah** klien tahu jawabannya asli atau fixture. |
| `device` | Selalu `"cpu"`. |
| `processing_ms` | Waktu proses di sisi service. |
| `scenario` | Nama skenario bila mock yang menjawab, `null` bila engine asli. |
| `debug` | Objek bebas atau `null`. Isinya **bukan** kontrak dan boleh berubah kapan saja. |

Modul menambahkan field `meta` miliknya sendiri di luar daftar ini.

---

## Skenario (khusus mock)

Selama sebuah modul dilayani engine mock, field opsional `scenario` memaksa fixture tertentu.
Bila tidak dikirim, satu skenario dipilih **deterministik dari hash isi berkas** — unggahan yang
sama selalu menghasilkan respons yang sama, sehingga klien Laravel punya data stabil untuk
dikembangkan.

Field ini diabaikan begitu engine asli aktif, dan `meta.scenario` menjadi `null`. Daftar
skenario yang tersedia berbeda per modul.

---

## CPU-only

Tidak ada jalur kode GPU di mana pun, dan `Dockerfile.ml` memastikannya saat build lewat
assertion pada `torch`. `meta.device` karenanya selalu `"cpu"` — itu jaminan, bukan kebetulan
konfigurasi.

---

## Yang dijamin stabil

Kode error, kode warning, `severity`, dan bentuk amplop error adalah **kontrak**. Menukar engine
mock dengan model asli tidak mengubah satu pun di antaranya; yang berubah hanya `meta.engine`.
