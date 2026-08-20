# Evaluasi Modul 1 — Document Parsing

Engine: `Qwen/Qwen2-VL-2B-Instruct` · 21 panggilan · 169 baris ground truth · rata-rata 299.1 detik per panggilan

Dihasilkan otomatis oleh `scripts/evaluate.py`. Jangan disunting tangan —
jalankan ulang harness-nya.

## Ringkasan

- **JSON terbaca**: 100.0% panggilan menghasilkan keluaran yang bisa diurai.
- **Recall baris**: 91.1% baris ground truth berhasil ditemukan.
- **Presisi baris**: 92.8% baris yang dikembalikan model benar-benar ada di dokumen.
- **Jumlah benar**: 100.0% dari baris yang ketemu punya jumlah yang tepat.

Angka **jumlah** adalah yang paling menentukan. Nama barang yang salah ketik masih
kelihatan oleh manusia; jumlah yang salah lolos begitu saja dan merusak cross-check.

## Menemukan baris

Penjodohan memakai kemiripan nama dengan ambang 0.80. Kolom *Nama persis* menghitung baris yang namanya sama tepat setelah normalisasi;
selisihnya terhadap *Recall* adalah baris yang terbaca tetapi ditulis sedikit berbeda.

| Kelompok | Dokumen | JSON terbaca | Recall baris | Presisi baris | Nama persis |
|---|---:|---:|---:|---:|---:|
| keseluruhan | 21 | 100.0% | 91.1% | 92.8% | 85.2% |
| image | 8 | 100.0% | 91.5% | 91.5% | 89.4% |
| pdf | 13 | 100.0% | 91.0% | 93.3% | 83.6% |

## Ketepatan isi baris

Penyebutnya adalah baris yang berhasil dijodohkan — jadi ini menjawab "dari yang ketemu, berapa yang dibaca dengan benar".

| Field | keseluruhan | image | pdf |
|---|---:|---:|---:|
| Jumlah | 100.0% | 100.0% | 100.0% |
| Satuan (apa adanya) | 97.4% | 100.0% | 96.4% |
| Satuan (normalisasi) | 97.4% | 100.0% | 96.4% |
| Isi per satuan | 74.0% | 72.1% | 74.8% |
| SKU | 22.7% | 27.9% | 20.7% |
| Halaman asal | 94.2% | 79.1% | 100.0% |

## Field tingkat dokumen

Hanya dinilai pada panggilan yang memang memuat kop surat (PDF utuh, atau halaman pertama untuk sumber foto).

| Field | keseluruhan | image | pdf |
|---|---:|---:|---:|
| Jenis dokumen | 100.0% | 100.0% | 100.0% |
| Nomor dokumen | 100.0% | 100.0% | 100.0% |
| Tanggal | 100.0% | 100.0% | 100.0% |
| Pengirim | 77.8% | 80.0% | 76.9% |
| Penerima | 94.4% | 100.0% | 92.3% |
| Jumlah halaman | 83.3% | 40.0% | 100.0% |

## Pengaruh kualitas gambar

`—` berarti dokumen bersih tanpa degradasi.

| Kelompok | Dokumen | JSON terbaca | Recall baris | Presisi baris | Nama persis |
|---|---:|---:|---:|---:|---:|
| heavy | 6 | 100.0% | 100.0% | 100.0% | 97.1% |
| light | 2 | 100.0% | 66.7% | 66.7% | 66.7% |
| — | 13 | 100.0% | 91.0% | 93.3% | 83.6% |

| Field | heavy | light | — |
|---|---:|---:|---:|
| Jumlah | 100.0% | 100.0% | 100.0% |
| Satuan (apa adanya) | 100.0% | 100.0% | 96.4% |
| Satuan (normalisasi) | 100.0% | 100.0% | 96.4% |
| Isi per satuan | 68.6% | 87.5% | 74.8% |
| SKU | 25.7% | 37.5% | 20.7% |
| Halaman asal | 80.0% | 75.0% | 100.0% |

## Apakah confidence bisa dipercaya?

Rata-rata confidence baris **benar**: 97.9% (n=144) · baris **salah**: 95.9% (n=10)

Selisihnya hanya 2.1 poin. Confidence nyaris tidak membedakan baris benar dari baris salah, jadi angka itu **belum layak** dipakai untuk memutuskan baris mana yang perlu diperiksa manusia. Perlu ditinjau ulang sebelum UI menyandarkan apa pun padanya.

## Catatan

- Sampel: 13 dokumen, 21 panggilan engine. Dataset penuh berisi 200 dokumen; jalankan tanpa `--sample` untuk seluruhnya.
- Penjodohan baris memakai kemiripan teks, bukan pemahaman makna. Dua produk dengan nama sangat mirip berpotensi tertukar.
- Satuan pada dataset sintetis sengaja diacak (mis. minyak goreng dalam 'Zak'), sehingga model tidak bisa menebak satuan dari pengetahuan umum. Itu memang disengaja, tetapi membuat angka satuan lebih pesimistis daripada dokumen nyata.
