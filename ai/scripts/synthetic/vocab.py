"""Kosakata logistik Indonesia untuk generator Surat Jalan sintetis.

Dipisah dari kode render supaya variasi bahasa bisa ditambah tanpa menyentuh
layout. Nilai-nilai di sini sengaja meniru dokumen nyata: satuan campuran,
label yang tidak konsisten antar-perusahaan, dan format nomor yang berbeda-beda.
"""

from __future__ import annotations

from app.modules.document.schemas import UnitNormalized

# --- Satuan -------------------------------------------------------------
# Kunci = tulisan pada dokumen (unit_raw), nilai = enum kontrak.
# 'Ball', 'Slop', 'Renceng' sengaja dipetakan ke UNKNOWN: satuan ini dipakai
# di lapangan tapi di luar enum, dan justru kasus inilah yang harus teruji.
UNIT_MAP: dict[str, UnitNormalized] = {
    "Pcs": UnitNormalized.PCS,
    "Unit": UnitNormalized.PCS,
    "Box": UnitNormalized.BOX,
    "Dus": UnitNormalized.BOX,
    "Pack": UnitNormalized.BOX,
    "Karton": UnitNormalized.KARTON,
    "Ktn": UnitNormalized.KARTON,
    "Koli": UnitNormalized.KOLI,
    "Kg": UnitNormalized.KG,
    "Lusin": UnitNormalized.LUSIN,
    "Roll": UnitNormalized.ROLL,
    "Sak": UnitNormalized.SAK,
    "Zak": UnitNormalized.SAK,
    "Ball": UnitNormalized.UNKNOWN,
    "Slop": UnitNormalized.UNKNOWN,
    "Renceng": UnitNormalized.UNKNOWN,
}

# Satuan yang wajar punya isi per satuan (mis. '10 karton @ 12 pcs').
UNITS_WITH_CONTENTS = ("Box", "Dus", "Pack", "Karton", "Ktn", "Koli", "Ball", "Slop", "Lusin")

# --- Produk FMCG --------------------------------------------------------
PRODUCTS: tuple[tuple[str, str], ...] = (
    ("Minyak Goreng Sania 2L", "SNA"),
    ("Minyak Goreng Bimoli 1L", "BML"),
    ("Beras Premium Ramos 5kg", "BRS"),
    ("Gula Pasir Gulaku 1kg", "GLK"),
    ("Tepung Terigu Segitiga Biru 1kg", "TRG"),
    ("Kecap Manis Bango 600ml", "BNG"),
    ("Saos Sambal ABC 335ml", "ABC"),
    ("Mie Instan Indomie Goreng", "IDM"),
    ("Mie Sedaap Soto", "MSD"),
    ("Kopi Kapal Api Special 165g", "KKA"),
    ("Teh Botol Sosro 250ml", "SSR"),
    ("Susu UHT Ultra Milk 250ml", "ULT"),
    ("Susu Kental Manis Frisian Flag", "FRF"),
    ("Sabun Mandi Lifebuoy 85g", "LFB"),
    ("Deterjen Rinso Anti Noda 770g", "RNS"),
    ("Pasta Gigi Pepsodent 190g", "PPS"),
    ("Tisu Paseo Smart 250 sheet", "PSO"),
    ("Air Mineral Aqua 600ml", "AQA"),
    ("Biskuit Roma Kelapa 300g", "ROM"),
    ("Sarden ABC Saos Tomat 425g", "SRD"),
    ("Garam Beryodium Dolphin 250g", "DLP"),
    ("Santan Kara 200ml", "KRA"),
)

# --- Perusahaan ---------------------------------------------------------
COMPANY_PREFIXES = ("PT", "CV", "UD", "Toko", "Koperasi")
COMPANY_WORDS = (
    "Sinar Terang", "Cahaya Abadi", "Mitra Boga", "Nusantara Logistik",
    "Anugerah Pangan", "Berkah Sentosa", "Makmur Jaya", "Sumber Rejeki",
    "Tunas Harapan", "Karya Mandiri", "Sejahtera Utama", "Bintang Timur",
    "Surya Kencana", "Panca Niaga", "Dwi Perkasa", "Rukun Santosa",
)

# --- Label yang bervariasi antar-perusahaan -----------------------------
TITLES = ("SURAT JALAN", "Surat Jalan", "SURAT JALAN / DELIVERY ORDER", "SURAT PENGANTAR BARANG")
LABEL_NUMBER = ("No. Surat Jalan", "Nomor", "No. SJ", "No.", "Nomor Surat Jalan")
LABEL_DATE = ("Tanggal", "Tgl.", "Tanggal Kirim", "Tgl")
LABEL_SENDER = ("Pengirim", "Dari", "Dikirim Oleh")
LABEL_RECIPIENT = ("Kepada Yth.", "Penerima", "Kepada", "Tujuan")
LABEL_ITEM = ("Nama Barang", "Deskripsi Barang", "Uraian Barang", "Nama Produk")
LABEL_QTY = ("Qty", "Jumlah", "Banyaknya", "Kuantitas")
LABEL_UNIT = ("Satuan", "Sat.", "Unit")
LABEL_SKU = ("Kode", "Kode Barang", "SKU", "Part No.")

FOOTER_NOTES = (
    "Barang yang sudah diterima tidak dapat dikembalikan.",
    "Mohon periksa barang sebelum menandatangani surat jalan ini.",
    "Surat jalan ini merupakan bukti pengiriman yang sah.",
    "Barang diterima dalam keadaan baik dan sesuai jumlah.",
)
SIGNATURE_LABELS = (
    ("Pengirim", "Penerima"),
    ("Hormat Kami", "Diterima Oleh"),
    ("Petugas Gudang", "Penerima Barang"),
)

MONTHS_ID = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
ROMAN_MONTHS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
