# Evaluasi Modul 1 — Document Parsing

Engine: `Qwen/Qwen2-VL-2B-Instruct` · 129 panggilan · 899 baris ground truth · rata-rata 262.3 detik per panggilan

Dihasilkan otomatis oleh `scripts/evaluate.py`. Jangan disunting tangan —
jalankan ulang harness-nya.

## Ringkasan

- **JSON terbaca**: 96.1% panggilan menghasilkan keluaran yang bisa diurai.
- **Recall baris**: 94.0% baris ground truth berhasil ditemukan.
- **Presisi baris**: 100.0% baris yang dikembalikan model benar-benar ada di dokumen.
- **Jumlah benar**: 97.4% dari baris yang ketemu punya jumlah yang tepat.

Angka **jumlah** adalah yang paling menentukan. Nama barang yang salah ketik masih
kelihatan oleh manusia; jumlah yang salah lolos begitu saja dan merusak cross-check.

## Menemukan baris

Penjodohan memakai kemiripan nama dengan ambang 0.80, lalu sapuan kedua memakai jumlah+satuan untuk baris yang namanya meleset.

*Recall* = barisnya ketemu, dengan cara apa pun. *Nama terbaca* = dari baris yang ketemu, berapa yang ketemu lewat namanya sendiri — kurang dari 100% berarti model menemukan baris dan menulis angkanya dengan benar, tetapi mengisi kolom nama dengan hal lain (mis. kode barang). *Nama persis* lebih ketat lagi: ejaannya sama tepat.

| Kelompok | Dokumen | JSON terbaca | Recall baris | Presisi baris | Nama terbaca | Nama persis |
|---|---:|---:|---:|---:|---:|---:|
| keseluruhan | 129 | 96.1% | 94.0% | 100.0% | 95.6% | 85.0% |
| image | 64 | 92.2% | 86.5% | 100.0% | 98.7% | 76.1% |
| pdf | 65 | 100.0% | 98.9% | 100.0% | 93.9% | 90.8% |

## Ketepatan isi baris

Penyebutnya adalah baris yang berhasil dijodohkan — jadi ini menjawab "dari yang ketemu, berapa yang dibaca dengan benar".

| Field | keseluruhan | image | pdf |
|---|---:|---:|---:|
| Jumlah | 97.4% | 94.5% | 99.1% |
| Satuan (apa adanya) | 94.2% | 88.3% | 97.6% |
| Satuan (normalisasi) | 95.0% | 90.3% | 97.8% |
| Isi per satuan | 56.8% | 51.9% | 59.6% |
| SKU | 83.9% | 72.7% | 90.3% |
| Halaman asal | 92.3% | 78.9% | 100.0% |

## Field tingkat dokumen

Hanya dinilai pada panggilan yang memang memuat kop surat (PDF utuh, atau halaman pertama untuk sumber foto).

| Field | keseluruhan | image | pdf |
|---|---:|---:|---:|
| Jenis dokumen | 95.4% | 88.4% | 100.0% |
| Nomor dokumen | 88.9% | 76.7% | 96.9% |
| Tanggal | 94.4% | 86.0% | 100.0% |
| Pengirim | 61.1% | 51.2% | 67.7% |
| Penerima | 64.8% | 60.5% | 67.7% |
| Jumlah halaman | 100.0% | — | 100.0% |

## Pengaruh kualitas gambar

`—` berarti dokumen bersih tanpa degradasi.

| Kelompok | Dokumen | JSON terbaca | Recall baris | Presisi baris | Nama terbaca | Nama persis |
|---|---:|---:|---:|---:|---:|---:|
| heavy | 25 | 84.0% | 82.3% | 100.0% | 100.0% | 70.1% |
| light | 18 | 100.0% | 98.0% | 100.0% | 95.9% | 92.0% |
| medium | 21 | 95.2% | 81.7% | 100.0% | 100.0% | 69.7% |
| — | 65 | 100.0% | 98.9% | 100.0% | 93.9% | 90.8% |

| Field | heavy | light | medium | — |
|---|---:|---:|---:|---:|
| Jumlah | 91.7% | 96.9% | 95.5% | 99.1% |
| Satuan (apa adanya) | 81.0% | 93.9% | 92.1% | 97.6% |
| Satuan (normalisasi) | 84.3% | 94.9% | 93.3% | 97.8% |
| Isi per satuan | 49.6% | 52.0% | 55.1% | 59.6% |
| SKU | 64.5% | 88.8% | 66.3% | 90.3% |
| Halaman asal | 77.7% | 84.7% | 74.2% | 100.0% |

## Apakah confidence bisa dipercaya?

Confidence hanya berguna kalau angkanya berbeda antara baris benar dan baris salah.
Kolom *Selisih* itulah ukurannya; mendekati nol berarti angkanya tidak memberi tahu
apa-apa. Tiga kandidat rumus diukur berdampingan dari run yang sama.

| Rumus | Baris benar | Baris salah | Selisih | n benar | n salah |
|---|---:|---:|---:|---:|---:|
| Rata-rata atas nama (dipakai kontrak) | 97.9% | 93.5% | +4.4 poin | 747 | 98 |
| Token terlemah pada nama | 86.3% | 68.1% | +18.2 poin | 747 | 98 |
| Rata-rata atas jumlah | 99.2% | 96.9% | +2.3 poin | 747 | 98 |

Yang dipakai kontrak saat ini adalah **rata-rata atas nama barang**: benar 97.9% vs salah 93.5%.

Selisihnya hanya 4.4 poin. Confidence nyaris tidak membedakan baris benar dari baris salah, jadi angka itu **belum layak** dipakai untuk memutuskan baris mana yang perlu diperiksa manusia. Perlu ditinjau ulang sebelum UI menyandarkan apa pun padanya.

## Catatan

- Sampel: 65 dokumen, 129 panggilan engine. Dataset penuh berisi 200 dokumen; jalankan tanpa `--sample` untuk seluruhnya.
- Penjodohan baris memakai kemiripan teks, bukan pemahaman makna. Dua produk dengan nama sangat mirip berpotensi tertukar.
- Satuan pada dataset sintetis sengaja diacak (mis. minyak goreng dalam 'Zak'), sehingga model tidak bisa menebak satuan dari pengetahuan umum. Itu memang disengaja, tetapi membuat angka satuan lebih pesimistis daripada dokumen nyata.
