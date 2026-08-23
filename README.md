# CrossInspect AI

Verifikasi silang otomatis untuk penerimaan barang gudang: bandingkan **Surat Jalan** dengan
**foto tumpukan barang**, lalu laporkan apakah keduanya cocok.

Dikerjakan untuk **AI Innovation Challenge | COMPFEST 18**, tema *AI for the Backbone of the
Economy*, kategori Smart Logistics.

---

## Masalahnya

Penerimaan barang di gudang UMKM masih dicocokkan manual, satu per satu, antara fisik barang dan
dokumen pengiriman. Lambat, dan salah hitung yang tidak disadari berujung kerugian yang baru
ketahuan jauh belakangan.

## Cara kerjanya

```
[ Foto Surat Jalan ] ──> Modul 1  Document Parsing ──┐
                                                      ├──> Modul 3  Cross-Check ──> Vonis
[ Foto tumpukan   ] ──> Modul 2  Physical Inspection ─┘
```

| Modul | Peran | Model |
|---|---|---|
| 1. Document Parsing | Ekstraksi barang & jumlah dari Surat Jalan / Invoice | Qwen2-VL-2B (CPU) |
| 2. Physical Inspection | Menghitung kemasan pada foto | YOLO, fine-tuned |
| 3. Cross-Check | Merekonsiliasi keduanya | murni aturan, tanpa model |

Modul 3 sengaja tidak memuat model. Ia menerima dua respons JSON dan menjawab dalam milidetik,
sehingga vonis tidak ikut menunggu inference dokumen yang mahal.

---

## Instalasi

**Prasyarat:** Docker Desktop (alokasikan minimal 4 GB memori) dan Git. PHP, Composer, maupun
Node tidak perlu dipasang di mesin, melainkan semuanya berjalan di dalam container.

**1. Clone dan siapkan konfigurasi**

```bash
git clone https://github.com/Federico2884/CrossInspect-AIC.git
cd CrossInspect-AIC
cp .env.example .env
```

**2. Pasang dependensi PHP**

Langkah ini tidak bisa dilewati: `compose.yaml` membangun image Laravel dari
`vendor/laravel/sail/runtimes/8.5`, sedangkan `vendor/` tidak ikut di repo. Jadi `vendor` harus
ada **sebelum** `docker compose` dijalankan.

```bash
docker run --rm -v "$(pwd):/app" -w /app composer:latest install --ignore-platform-reqs
```

**3. Nyalakan container**

```bash
./vendor/bin/sail up -d --build
```

**4. Siapkan aplikasi**

```bash
./vendor/bin/sail artisan key:generate
touch database/database.sqlite
./vendor/bin/sail artisan migrate --force
./vendor/bin/sail npm install
./vendor/bin/sail npm run build
```

`./vendor/bin/sail` hanyalah pembungkus tipis. Kalau lebih nyaman, tiap perintah di atas bisa
dijalankan langsung tanpa Sail:

```bash
docker compose exec laravel.test <perintah>
```

Langkah `npm run build` menyusun CSS dan JS — tanpa itu halaman tampil tanpa gaya sama sekali,
karena `public/build` juga tidak ikut di repo.

---

## Menjalankan

Setelah terpasang, cukup:

```bash
./vendor/bin/sail up -d
```

Buka **http://localhost**. Tidak perlu API key, tidak perlu unduhan tambahan, bobot YOLO ikut
di dalam repo.

| Halaman | Isi |
|---|---|
| `/` | Alur utama: unggah Surat Jalan + foto barang, dapatkan vonis |
| `/demo` | Percobaan tanpa menyiapkan berkas, memilih skenario, pakai contoh bawaan |
| `/documents` | Halaman uji Modul 1 saja |

**`/demo`.** Konfigurasi bawaan menggunakan engine *mock*, sehingga halaman tersebut memberi
gambaran alurnya dalam hitungan detik.

### Menghidupkan model sungguhan

Bawaannya mock supaya `docker compose up` tetap ringan dan cepat. Untuk inference asli:

```bash
AI_DOCKERFILE=Dockerfile.ml AI_ENGINE=qwen2vl docker compose up -d --build
```

Perlu diketahui sebelum mencoba: image ini memuat torch dan transformers, dan Qwen2-VL mengunduh
bobot sekitar 4 GB pada jalan pertama. Menyusun image-nya saja sudah menuntut memori — pada mesin
dengan Docker dijatah di bawah 4 GB, proses build bisa dimatikan paksa di tengah jalan. Inference
Qwen2-VL di CPU juga memakan waktu sekitar 200 detik per halaman; angka terukurnya ada di
[`ai/README.md`](ai/README.md).

Modul 2 tidak menuntut sebanyak itu. Bobot YOLO hanya 6 MB dan sudah ikut di repo, jadi kalau
yang ingin dicoba hanya perhitungan fisik, `AI_ENGINE` boleh dibiarkan `mock`:

```bash
AI_DOCKERFILE=Dockerfile.ml docker compose up -d --build
```

---

## Yang sudah bisa dan yang belum

Dokumen konsep berisi tiga parameter verifikasi:

| Parameter | Status |
|---|---|
| **Kuantitas** | (Sudah) berjalan tetapi membandingkan **total**. Akurasi MAP juga masih seadanya (bisa ditingkatkan) |
| **Identitas produk** | (Belum) model vision masih satu kelas (`packages`), sehingga varian tidak bisa dibedakan |
| **Integritas fisik** | (Belum) belum ada model deteksi kerusakan, sehingga `defect.status` selalu `unavailable`. Menjadi fitur tambahan yang belum diimplementasikan saat ini |

Sistem menyatakan keterbatasan ini secara eksplisit di responsnya, bukan mendiamkannya. Baris
bersatuan `kg`, `sak`, atau satuan tak dikenal dikeluarkan dari perhitungan dengan alasan yang
disebutkan, sehingga tidak memaksa dibandingkan lalu melaporkan selisih yang salah.

Batasan lain yang diketahui:

- **Hitungan visual adalah batas bawah.** Kemasan di baris belakang tumpukan tidak tertangkap
  kamera *line-of-sight*. Karena itu ada peringatan `POSSIBLE_OCCLUSION`.
- **Dokumen banyak halaman belum realistis** lewat request sinkron, mengingat latensi di atas.

Rincian tiap batasan ada di [`ai/README.md`](ai/README.md) dan kontrak masing-masing modul.

---

## Dokumentasi

| Berkas | Isi |
|---|---|
| [`ai/README.md`](ai/README.md) | Menjalankan service, memilih engine, angka latensi terukur |
| [`ai/CONTRACT.md`](ai/CONTRACT.md) | Konvensi bersama: amplop error, `meta`, warning vs error |
| [`ai/app/modules/*/CONTRACT.md`](ai/app/modules) | Kontrak API tiap modul |
| [`ai/EVALUATION.md`](ai/EVALUATION.md) | Cara akurasi Modul 1 diukur |
| [`ai/scripts/README.md`](ai/scripts/README.md) | Generator Surat Jalan sintetis |

Kontrak tinggal di sebelah `schemas.py` yang menegakkannya. Kalau keduanya berbeda, **modelnya
yang benar** dan dokumennya yang salah.

---

## Pengembangan

```bash
# Test Python (ketiga modul)
docker compose --profile test run --rm ai-test python -m pytest -q

# Test Laravel
./vendor/bin/sail test
```

Arsitekturnya memakai satu pola berulang: tiap modul menaruh engine di balik antarmuka yang sama
(`engines/base.py`), dengan mock deterministik sebagai implementasi kedua. Menukar mock dengan
model asli tidak mengubah bentuk respons, hanya `meta.engine`. Hal ini membuat klien Laravel
bisa dikerjakan paralel dengan modelnya, dan yang membuat seluruh logika bisa diuji tanpa GPU.
