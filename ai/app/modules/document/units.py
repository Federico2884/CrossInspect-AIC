"""Normalisasi satuan dari tulisan bebas menjadi ``UnitNormalized``.

Modul ini sengaja tidak mengimpor torch: engine asli boleh memakainya, tetapi
isinya murni pemetaan teks sehingga bisa diuji di image test yang ringan.

``unit_raw`` tidak pernah diubah — yang dinormalisasi hanya nilai turunannya.
Satuan yang tidak dikenali jatuh ke ``UNKNOWN``, dan itu keputusan yang benar:
lebih baik konsumen tahu satuannya di luar daftar daripada dipaksakan ke enum
yang salah. Lihat catatan satuan di ``CONTRACT.md``.

Peta di sini harus tetap sepakat dengan ``scripts/synthetic/vocab.py`` yang
memberi label dataset step 3. Kesepakatan itu dijaga oleh test, bukan oleh
impor silang — ``vocab.py`` khusus generator dan tidak ikut ke image runtime.
"""

from __future__ import annotations

import re

from app.modules.document.schemas import UnitNormalized

# Satuan yang lazim di gudang tetapi berada di luar enum. Didaftarkan eksplisit
# supaya terlihat bahwa UNKNOWN-nya disengaja, bukan karena luput dari peta.
DELIBERATELY_UNKNOWN = frozenset({"ball", "slop", "renceng"})

_UNIT_MAP: dict[str, UnitNormalized] = {
    # pcs
    "pcs": UnitNormalized.PCS,
    "pc": UnitNormalized.PCS,
    "piece": UnitNormalized.PCS,
    "pieces": UnitNormalized.PCS,
    "unit": UnitNormalized.PCS,
    "buah": UnitNormalized.PCS,
    "bh": UnitNormalized.PCS,
    "ekor": UnitNormalized.PCS,
    # box
    "box": UnitNormalized.BOX,
    "boxes": UnitNormalized.BOX,
    "dus": UnitNormalized.BOX,
    "dos": UnitNormalized.BOX,
    "pack": UnitNormalized.BOX,
    "pak": UnitNormalized.BOX,
    "paket": UnitNormalized.BOX,
    # karton
    "karton": UnitNormalized.KARTON,
    "ktn": UnitNormalized.KARTON,
    "carton": UnitNormalized.KARTON,
    "krt": UnitNormalized.KARTON,
    # koli
    "koli": UnitNormalized.KOLI,
    "kol": UnitNormalized.KOLI,
    # kg
    "kg": UnitNormalized.KG,
    "kgs": UnitNormalized.KG,
    "kilo": UnitNormalized.KG,
    "kilogram": UnitNormalized.KG,
    # lusin
    "lusin": UnitNormalized.LUSIN,
    "lsn": UnitNormalized.LUSIN,
    "dozen": UnitNormalized.LUSIN,
    "dz": UnitNormalized.LUSIN,
    # roll
    "roll": UnitNormalized.ROLL,
    "rol": UnitNormalized.ROLL,
    "gulung": UnitNormalized.ROLL,
    # sak
    "sak": UnitNormalized.SAK,
    "zak": UnitNormalized.SAK,
    "sack": UnitNormalized.SAK,
    "karung": UnitNormalized.SAK,
}

# Titik, koma, dan spasi berlebih sering ikut terbawa dari OCR/model ("Ktn.",
# "kg ", "Dus,"). Angka juga dibuang supaya "12 pcs" tetap terbaca sebagai pcs.
_CLEAN = re.compile(r"[^a-z]+")


def _canonical(raw: str) -> str:
    return _CLEAN.sub("", raw.strip().lower())


def normalize_unit(raw: str | None) -> UnitNormalized:
    """Petakan satuan apa adanya ke enum. Tidak dikenali -> ``UNKNOWN``."""
    if not raw:
        return UnitNormalized.UNKNOWN

    key = _canonical(raw)
    if not key:
        return UnitNormalized.UNKNOWN

    if key in _UNIT_MAP:
        return _UNIT_MAP[key]

    # Bentuk jamak sederhana: "kartons", "dus2" sudah bersih dari angka di atas.
    if key.endswith("s") and key[:-1] in _UNIT_MAP:
        return _UNIT_MAP[key[:-1]]

    return UnitNormalized.UNKNOWN
