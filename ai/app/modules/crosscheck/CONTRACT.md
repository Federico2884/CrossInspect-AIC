# Kontrak API Cross-Check

Kontrak resmi untuk **Modul 3 (Cross-Check Engine)** CrossInspect AI.
Ditegakkan oleh model Pydantic di [`schemas.py`](schemas.py); kalau dokumen ini dan model
tersebut sampai berbeda, modelnya yang benar dan dokumen ini yang salah.

Dokumen ini hanya memuat yang **khas Modul 3**. Aturan yang berlaku di semua modul ada di
[`CONTRACT.md`](../../../CONTRACT.md) induk.

---

## Yang membedakan modul ini

Modul 1 dan 2 menerima berkas dan menjalankan model. **Modul 3 tidak menyentuh model sama
sekali** — ia menerima dua respons JSON yang sudah jadi, lalu merekonsiliasinya. Konsekuensinya:

- Tidak ada unggahan, tidak ada magic bytes, tidak ada batas 20 MB.
- Jawabannya **instan** (< 5 ms), bukan ~200 detik seperti Modul 1.
- Bisa diuji penuh tanpa torch, tanpa bobot, tanpa HTTP.

Pemisahan ini disengaja. Kalau satu endpoint memanggil kedua model, ia mewarisi latensi
terburuk — request tertahan menit-menitan padahal sisi vision selesai dalam milidetik. Dengan
bentuk ini, Laravel bisa menampilkan hasil vision lebih dulu sambil menunggu dokumen, lalu
meminta vonis begitu keduanya tiba.

---

## Endpoint

```
POST http://ai:8000/crosscheck
Content-Type: application/json
```

Dari host (untuk debugging): `http://localhost:8001/crosscheck`.

Body-nya adalah **dua respons apa adanya**, tanpa diubah:

```json
{
  "document": { "…respons utuh dari POST /document/parse…" },
  "vision":   { "…respons utuh dari POST /vision/inspect…" }
}
```

Klien tidak perlu memilih field. Teruskan saja keduanya — modul ini yang tahu bagian mana yang
relevan, dan itu satu-satunya tempat pengetahuan tersebut boleh tinggal.

---

## Respons — 200

```json
{
  "status": "MISMATCH",
  "quantity": {
    "document_total": 17,
    "detected_total": 15,
    "difference": -2,
    "counted_items": [
      { "item_index": 0, "item_name": "Susu UHT Ultra 250ml", "quantity": 10,
        "unit_raw": "Karton", "unit_normalized": "karton" }
    ],
    "excluded_items": [
      { "item_index": 2, "item_name": "Gula Pasir", "quantity": 50,
        "unit_raw": "Kg", "unit_normalized": "kg", "reason": "UNIT_IS_WEIGHT" }
    ]
  },
  "identity":  { "status": "unavailable", "reason": "Model vision hanya mengenal satu kelas." },
  "integrity": { "status": "unavailable", "reason": "Model kerusakan belum tersedia." },
  "warnings": [
    { "code": "PARTIAL_COVERAGE", "message": "…", "severity": "warning", "item_index": 2 }
  ],
  "meta": { "engine": "rules", "device": "cpu", "processing_ms": 1,
            "document_engine": "qwen2vl", "vision_engine": "yolo", "scenario": null, "debug": null }
}
```

### `status`

| Nilai | Arti |
|---|---|
| `MATCH` | Semua baris bisa diverifikasi, dan totalnya cocok. |
| `PARTIAL` | Baris yang bisa diverifikasi cocok, tetapi ada baris yang **tidak** bisa diperiksa. |
| `MISMATCH` | Ada selisih antara total dokumen dan hitungan fisik. |
| `UNVERIFIABLE` | Tidak ada satu pun baris yang bisa diverifikasi, atau hitungan visualnya tidak layak dipercaya. |

`PARTIAL` sengaja dipisahkan dari `MATCH`. Menyebut "cocok" padahal separuh kiriman tidak
pernah diperiksa adalah jaminan palsu — dan bagi petugas gudang, jaminan palsu lebih berbahaya
daripada ketidaktahuan yang jujur.

### `quantity`

| Field | Tipe | Keterangan |
|---|---|---|
| `document_total` | int ≥ 0 | Jumlah `quantity` dari baris yang **bisa** dihitung saja. |
| `detected_total` | int ≥ 0 | `detected_count` dari Modul 2, apa adanya. |
| `difference` | int | `detected_total − document_total`. Negatif berarti fisik lebih sedikit. |
| `counted_items[]` | array | Baris yang ikut dijumlahkan. |
| `excluded_items[]` | array | Baris yang dikecualikan, masing-masing dengan `reason`. |

`document_total` **bukan** jumlah seluruh baris di Surat Jalan. Ia hanya menjumlahkan yang
satuannya bisa dilihat kamera — lihat di bawah.

---

## Satuan mana yang bisa diverifikasi

Model Modul 2 mengenali satu kelas: `cardboard`. Ia menghitung **kemasan kardus terluar**. Maka
hanya satuan yang berarti "satu kardus" yang boleh dijumlahkan:

| `unit_normalized` | Ikut dihitung? | `reason` bila dikecualikan |
|---|---|---|
| `karton`, `box`, `koli` | ✅ | — |
| `kg` | ❌ | `UNIT_IS_WEIGHT` |
| `pcs`, `lusin`, `roll`, `sak` | ❌ | `UNIT_NOT_CARDBOARD` |
| `unknown` | ❌ | `UNIT_UNKNOWN` |

`sak` dan `roll` adalah benda fisik yang bisa dicacah, tetapi **bukan kardus** — model tidak
dilatih mengenalinya, jadi menjumlahkannya akan menciptakan selisih palsu. `unknown` mencakup
`ball`, `slop`, `renceng`: satuan Surat Jalan asli yang sengaja tidak dipetakan oleh Modul 1.

> **Ingat aritmetikanya.** Untuk `10 karton @ 12 pcs`, yang dijumlahkan adalah **`quantity`
> (10)**, bukan `total_pieces` (120). Kamera hanya melihat kemasan terluar; isi kardus yang
> tersegel tidak terlihat sama sekali.

---

## Identitas dan integritas

Dua dari tiga parameter di dokumen konsep **belum bisa dijawab**, dan modul ini menyatakannya
terus terang alih-alih diam:

| Parameter | `status` | Sebabnya |
|---|---|---|
| Identitas produk | `unavailable` | Model satu kelas — ia tahu ada 15 kardus, tidak tahu kardus apa. |
| Integritas fisik | `unavailable` | Tidak ada kelas kerusakan di model; `defect.status` dari Modul 2 selalu `unavailable`. |

Keduanya memakai bentuk yang sama (`status` + `reason`) dan akan berpindah dari `unavailable`
begitu modelnya tersedia — tanpa mengubah bentuk respons.

UI wajib menampilkan **"belum diperiksa"**, bukan "sesuai" atau "aman".

---

## Warning

Prinsip warning-vs-error ada di [kontrak induk](../../../CONTRACT.md#warning-vs-error).
Kode berikut khas Modul 3:

| Code | Severity | Arti |
|---|---|---|
| `IDENTITY_NOT_VERIFIED` | info | Selalu ada selama model masih satu kelas. |
| `INTEGRITY_NOT_VERIFIED` | info | Selalu ada selama model kerusakan belum tersedia. |
| `PARTIAL_COVERAGE` | warning | Ada baris yang dikecualikan; `item_index` menunjuk barisnya. |
| `NO_COUNTABLE_ITEMS` | error | Tidak ada baris berkardus sama sekali — kuantitas tidak bisa diverifikasi. |
| `COUNT_POSSIBLY_UNDERSTATED` | warning | Modul 2 melaporkan occlusion **dan** fisik lebih sedikit; selisihnya mungkin semu. |
| `COUNT_UNRELIABLE_UPSTREAM` | error | Modul 2 melaporkan `COUNT_UNRELIABLE`; hitungannya tidak dipakai. |
| `DOCUMENT_LOW_CONFIDENCE` | warning | Baris yang ikut dijumlahkan dibaca dengan confidence rendah oleh Modul 1. |
| `DOCUMENT_TYPE_UNKNOWN` | warning | Modul 1 tidak mengenali jenis dokumennya. |
| `NO_OBJECT_DETECTED_UPSTREAM` | error | Modul 2 tidak menemukan objek apa pun di foto. |

---

## Aturan vonis

Urutannya berlaku dari atas; yang pertama cocok menentukan `status`.

1. Modul 2 mengirim `COUNT_UNRELIABLE` → **`UNVERIFIABLE`**. Hitungan yang tidak dipercaya
   tidak bisa memvonis apa pun, dan memaksakannya hanya melahirkan tuduhan tanpa dasar.
2. Tidak ada baris berkardus → **`UNVERIFIABLE`** + `NO_COUNTABLE_ITEMS`.
3. `difference != 0` → **`MISMATCH`**. Bila Modul 2 juga melaporkan occlusion dan fisiknya
   lebih sedikit, selisih tetap dilaporkan, tetapi disertai `COUNT_POSSIBLY_UNDERSTATED`.
4. Ada baris dikecualikan → **`PARTIAL`**.
5. Selebihnya → **`MATCH`**.

Aturan 3 sengaja tidak menyembunyikan selisih saat occlusion terdeteksi. Occlusion menjelaskan
*mengapa* angkanya bisa meleset; ia tidak membuktikan kiriman utuh. Yang berhak menyimpulkan itu
petugas, bukan sistem.

---

## Error

Modul 3 tidak menerima unggahan, jadi kode error soal berkas tidak berlaku di sini.

| HTTP | Code | Penyebab |
|---|---|---|
| 422 | `INVALID_REQUEST` | Body bukan JSON valid, atau `document`/`vision` tidak sesuai bentuk kontraknya. |

Bentuk amplopnya sama dengan modul lain — lihat [kontrak induk](../../../CONTRACT.md#amplop-error).

---

## Jaminan stabilitas

Modul ini murni aturan; tidak ada model yang akan menggantikannya. Yang akan berubah:

- `identity.status` berpindah dari `unavailable` begitu model multi-kelas tersedia.
- `integrity.status` berpindah begitu model kerusakan tersedia.
- Daftar satuan yang bisa dihitung bisa bertambah bila model dilatih mengenali karung atau
  gulungan.

Ketiganya **bukan** perubahan breaking: bentuk responsnya sudah menampung semuanya sejak awal.
Kode warning, nilai `status`, dan pemisahan `counted_items` / `excluded_items` adalah kontrak.
