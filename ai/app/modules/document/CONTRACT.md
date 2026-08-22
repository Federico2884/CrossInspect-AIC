# Kontrak API Document Parsing

Kontrak resmi untuk **Modul 1 (Document Parsing)** CrossInspect AI.
Ditegakkan oleh model Pydantic di [`schemas.py`](schemas.py); kalau dokumen ini dan model
tersebut sampai berbeda, modelnya yang benar dan dokumen ini yang salah.

Dokumen ini hanya memuat yang **khas Modul 1**. Aturan yang berlaku di semua modul — batas
unggahan, amplop error, arti `meta`, pembedaan warning dari error — ada di
[`CONTRACT.md`](../../../CONTRACT.md) induk, dan sebaiknya dibaca lebih dulu.

Pembaca: siapa pun yang menulis klien Laravel. Kontrak ini sudah bisa dipakai hari ini —
endpoint-nya sudah hidup dan dilayani mock yang deterministik.

---

## Endpoint

```
POST http://ai:8000/document/parse
Content-Type: multipart/form-data
```

Dari host (untuk debugging): `http://localhost:8001/document/parse`.

| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `file` | file | ya | **PDF, PNG, atau JPEG.** Maksimal 20 MB. |
| `scenario` | string | tidak | **Khusus mock.** Memaksa fixture tertentu — lihat [Skenario](#skenario). |

PDF adalah satu-satunya format yang diterima Modul 1 tetapi ditolak Modul 2.

---

## Respons — 200

```json
{
  "document_type": "SURAT_JALAN",
  "document_number": "SJ/2026/08/00161",
  "document_date": "2026-08-15",
  "sender": "PT Cahaya Abadi",
  "recipient": "Toko Sumber Rejeki",
  "page_count": 1,
  "items": [
    {
      "item_name": "Susu UHT Ultra 250ml",
      "sku": "ULT-250",
      "quantity": 10,
      "unit_raw": "Karton",
      "unit_normalized": "karton",
      "quantity_per_unit": 12,
      "total_pieces": 120,
      "source_page": 1
    }
  ],
  "confidence": { "document_number": 0.93, "items": [0.95], "overall": 0.86 },
  "warnings": [
    { "code": "AMBIGUOUS_UNIT", "message": "…", "severity": "warning", "item_index": 2 }
  ],
  "meta": {
    "engine": "mock",
    "device": "cpu",
    "processing_ms": 3,
    "scenario": "mixed_units",
    "debug": null
  }
}
```

### Field

| Field | Tipe | Keterangan |
|---|---|---|
| `document_type` | `SURAT_JALAN` \| `INVOICE` \| `UNKNOWN` | `UNKNOWN` tetap mengembalikan 200 — periksa `warnings`. |
| `document_number` | string | String kosong kalau tidak terbaca, tidak pernah null. |
| `document_date` | string \| null | ISO `YYYY-MM-DD`. Null kalau tidak ada di dokumen. |
| `sender` / `recipient` | string \| null | |
| `page_count` | int ≥ 1 | Halaman yang benar-benar diproses (dibatasi 10). |
| `items[]` | array | Boleh kosong. |
| `confidence` | object | `document_number`, `items[]` (sejajar dengan `items`), `overall`. Semuanya 0.0–1.0. |
| `warnings[]` | array | Masalah kualitas parse. **Bukan** error. |
| `meta` | object | Field umum — lihat [kontrak induk](../../../CONTRACT.md#meta). Modul 1 tidak menambah field. |

### Field item

| Field | Tipe | Keterangan |
|---|---|---|
| `item_name` | string | |
| `sku` | string \| null | |
| `quantity` | int ≥ 0 | **Dalam satuan `unit_raw`, bukan dalam pieces.** |
| `unit_raw` | string | Apa adanya dari dokumen: `Koli`, `Dus`, `Ball`, `Zak`… |
| `unit_normalized` | enum | `pcs` \| `box` \| `karton` \| `koli` \| `kg` \| `lusin` \| `roll` \| `sak` \| `unknown` |
| `quantity_per_unit` | int \| null | Isi per satuan, misalnya `12` pada "10 karton @ 12 pcs". |
| `total_pieces` | int \| null | `quantity × quantity_per_unit`, kalau bisa diturunkan. |
| `source_page` | int ≥ 1 | Tidak pernah melebihi `page_count`. |

> **Catatan cross-check.** Modul 2 menghitung karton fisik. Untuk `10 karton @ 12 pcs`,
> bandingkan dengan **`quantity` (10)** — bukan `total_pieces` (120). Pemisahan ini ada
> justru supaya kedua sisi tidak perlu menebak angka mana yang sedang dibaca.

> **Catatan satuan.** `unit_normalized` adalah enum tertutup, jadi satuan yang tidak lazim
> akan jatuh ke `unknown` — tetapi `unit_raw` selalu menyimpan apa yang tertulis di dokumen.
> Surat Jalan asli memakai `koli`, `dus`, `zak`, `ball`, `slop`; jangan pernah menyandarkan
> logika hanya pada enum ketika isinya `unknown`.

---

## Warning

Prinsip warning-vs-error ada di [kontrak induk](../../../CONTRACT.md#warning-vs-error).
Kode berikut khas Modul 1:

| Code | Severity | Arti |
|---|---|---|
| `LOW_CONFIDENCE_ITEM` | warning | Barang terbaca dengan confidence rendah; `item_index` menunjuk ke barang tersebut. |
| `MISSING_DOCUMENT_DATE` | warning | Tanggal tidak ditemukan; `document_date` bernilai null. |
| `MISSING_FIELD` | info/warning | Ada field lain yang gagal diekstrak. |
| `AMBIGUOUS_UNIT` | warning | `unit_raw` tidak terpetakan ke enum; `unit_normalized` menjadi `unknown`. |
| `UNRECOGNISED_DOCUMENT_TYPE` | error | Bukan Surat Jalan maupun Invoice. |
| `PAGE_LIMIT_TRUNCATED` | warning | Dokumen melebihi batas 10 halaman. |
| `QUANTITY_MISMATCH` | warning | **Dicadangkan — belum dipancarkan engine mana pun.** Lihat catatan di bawah. |

> **Catatan `QUANTITY_MISMATCH`.** Kode ini sudah dipesan tempatnya, tetapi belum pernah
> dikirim: untuk membandingkan total yang tertulis di dokumen dengan hasil hitungan, engine
> harus lebih dulu mengekstrak total tercetak itu, dan sekarang belum. Jangan menulis
> penanganan khusus untuknya — kode ini tidak akan muncul sampai fitur tersebut dikerjakan.

## Error

Modul 1 tidak menambah kode error di luar [yang umum](../../../CONTRACT.md#amplop-error).
`UNSUPPORTED_FILE_TYPE` di sini berarti berkasnya bukan PDF, PNG, maupun JPEG.

---

## Skenario

Tujuh fixture mock. Cara kerjanya ada di [kontrak induk](../../../CONTRACT.md#skenario-khusus-mock).

| `scenario` | Yang diuji |
|---|---|
| `clean_surat_jalan` | Jalur normal, 3 barang, confidence tinggi |
| `invoice` | Tipe `INVOICE` lengkap dengan SKU |
| `multi_page` | 3 halaman, barang tersebar di beberapa `source_page` |
| `mixed_units` | `karton`/`koli`/`Ball`/`kg`, aritmetika `quantity_per_unit`, `AMBIGUOUS_UNIT` |
| `low_confidence` | Skor rendah per barang + `LOW_CONFIDENCE_ITEM` |
| `missing_fields` | `document_date`/`sender` bernilai null + warning, tetap 200 |
| `unknown_type` | `UNKNOWN`, tanpa barang, warning ber-severity `error` |

Bangun klien Laravel dengan `mixed_units` dan `low_confidence` lebih dulu — jalur normal
justru yang paling mudah; dua skenario itulah yang benar-benar menguji logika cross-check.

```bash
curl -F "file=@sample.pdf" -F "scenario=mixed_units" http://localhost:8001/document/parse
```

---

## Jaminan stabilitas

Mock dan Qwen2-VL duduk di balik antarmuka yang sama ([`engines/base.py`](engines/base.py)),
jadi menukar keduanya **tidak mengubah bentuk respons** — field, tipe, dan enum-nya sama persis.
Jaminan umum soal `meta` ada di [kontrak induk](../../../CONTRACT.md#yang-dijamin-stabil).

Yang khas Modul 1: pemisahan `quantity` / `total_pieces` dan kode warning di atas adalah
kontrak, bukan detail implementasi.
