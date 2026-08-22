# Evaluasi Modul 1 — Document Parsing

Engine: `Qwen/Qwen2-VL-2B-Instruct` · 21 panggilan · 169 baris ground truth · rata-rata 317.3 detik per panggilan

Dihasilkan otomatis oleh `scripts/evaluate.py`. Jangan disunting tangan —
jalankan ulang harness-nya.

## Ringkasan

- **JSON terbaca**: 100.0% panggilan menghasilkan keluaran yang bisa diurai.
- **Recall baris**: 97.6% baris ground truth berhasil ditemukan.
- **Presisi baris**: 99.4% baris yang dikembalikan model benar-benar ada di dokumen.
- **Jumlah benar**: 97.6% dari baris yang ketemu punya jumlah yang tepat.

Angka **jumlah** adalah yang paling menentukan. Nama barang yang salah ketik masih
kelihatan oleh manusia; jumlah yang salah lolos begitu saja dan merusak cross-check.

## Menemukan baris

Penjodohan memakai kemiripan nama dengan ambang 0.80, lalu sapuan kedua memakai jumlah+satuan untuk baris yang namanya meleset.

*Recall* = barisnya ketemu, dengan cara apa pun. *Nama terbaca* = dari baris yang ketemu, berapa yang ketemu lewat namanya sendiri — kurang dari 100% berarti model menemukan baris dan menulis angkanya dengan benar, tetapi mengisi kolom nama dengan hal lain (mis. kode barang). *Nama persis* lebih ketat lagi: ejaannya sama tepat.

| Kelompok | Dokumen | JSON terbaca | Recall baris | Presisi baris | Nama terbaca | Nama persis |
|---|---:|---:|---:|---:|---:|---:|
| keseluruhan | 21 | 100.0% | 97.6% | 99.4% | 96.4% | 94.1% |
| image | 8 | 100.0% | 95.7% | 100.0% | 97.8% | 93.6% |
| pdf | 13 | 100.0% | 98.4% | 99.2% | 95.8% | 94.3% |

## Ketepatan isi baris

Penyebutnya adalah baris yang berhasil dijodohkan — jadi ini menjawab "dari yang ketemu, berapa yang dibaca dengan benar".

| Field | keseluruhan | image | pdf |
|---|---:|---:|---:|
| Jumlah | 97.6% | 93.3% | 99.2% |
| Satuan (apa adanya) | 93.9% | 86.7% | 96.7% |
| Satuan (normalisasi) | 93.9% | 86.7% | 96.7% |
| Isi per satuan | 67.3% | 71.1% | 65.8% |
| SKU | 91.5% | 80.0% | 95.8% |
| Halaman asal | 94.5% | 80.0% | 100.0% |

## Field tingkat dokumen

Hanya dinilai pada panggilan yang memang memuat kop surat (PDF utuh, atau halaman pertama untuk sumber foto).

| Field | keseluruhan | image | pdf |
|---|---:|---:|---:|
| Jenis dokumen | 100.0% | 100.0% | 100.0% |
| Nomor dokumen | 100.0% | 100.0% | 100.0% |
| Tanggal | 100.0% | 100.0% | 100.0% |
| Pengirim | 66.7% | 60.0% | 69.2% |
| Penerima | 83.3% | 100.0% | 76.9% |
| Jumlah halaman | 100.0% | — | 100.0% |

## Pengaruh kualitas gambar

`—` berarti dokumen bersih tanpa degradasi.

| Kelompok | Dokumen | JSON terbaca | Recall baris | Presisi baris | Nama terbaca | Nama persis |
|---|---:|---:|---:|---:|---:|---:|
| heavy | 6 | 100.0% | 97.1% | 100.0% | 100.0% | 97.1% |
| light | 2 | 100.0% | 91.7% | 100.0% | 90.9% | 83.3% |
| — | 13 | 100.0% | 98.4% | 99.2% | 95.8% | 94.3% |

| Field | heavy | light | — |
|---|---:|---:|---:|
| Jumlah | 91.2% | 100.0% | 99.2% |
| Satuan (apa adanya) | 85.3% | 90.9% | 96.7% |
| Satuan (normalisasi) | 85.3% | 90.9% | 96.7% |
| Isi per satuan | 82.4% | 36.4% | 65.8% |
| SKU | 76.5% | 90.9% | 95.8% |
| Halaman asal | 79.4% | 81.8% | 100.0% |

## Apakah confidence bisa dipercaya?

Rata-rata confidence baris **benar**: 98.0% (n=155) · baris **salah**: 96.0% (n=10)

Selisihnya hanya 2.0 poin. Confidence nyaris tidak membedakan baris benar dari baris salah, jadi angka itu **belum layak** dipakai untuk memutuskan baris mana yang perlu diperiksa manusia. Perlu ditinjau ulang sebelum UI menyandarkan apa pun padanya.

## Catatan

- Sampel: 13 dokumen, 21 panggilan engine. Dataset penuh berisi 200 dokumen; jalankan tanpa `--sample` untuk seluruhnya.
- Penjodohan baris memakai kemiripan teks, bukan pemahaman makna. Dua produk dengan nama sangat mirip berpotensi tertukar.
- Satuan pada dataset sintetis sengaja diacak (mis. minyak goreng dalam 'Zak'), sehingga model tidak bisa menebak satuan dari pengetahuan umum. Itu memang disengaja, tetapi membuat angka satuan lebih pesimistis daripada dokumen nyata.
