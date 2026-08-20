"""Test normalisasi satuan.

Yang dijaga bukan kelengkapan kamus, melainkan dua hal yang bisa merusak
cross-check: satuan yang salah dipetakan, dan kesepakatan dengan label dataset
step 3.
"""

import pytest

from app.modules.document.schemas import UnitNormalized
from app.modules.document.units import normalize_unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Pcs", UnitNormalized.PCS),
        ("pcs", UnitNormalized.PCS),
        ("PCS", UnitNormalized.PCS),
        ("Karton", UnitNormalized.KARTON),
        ("Ktn.", UnitNormalized.KARTON),
        ("  karton  ", UnitNormalized.KARTON),
        ("Dus", UnitNormalized.BOX),
        ("Zak", UnitNormalized.SAK),
        ("Kg", UnitNormalized.KG),
        ("kg.", UnitNormalized.KG),
        ("Lusin", UnitNormalized.LUSIN),
        ("Koli", UnitNormalized.KOLI),
        ("Roll", UnitNormalized.ROLL),
    ],
)
def test_common_units_map_to_the_enum(raw: str, expected: UnitNormalized):
    assert normalize_unit(raw) == expected


@pytest.mark.parametrize("raw", ["Ball", "Slop", "Renceng", "ball", "SLOP"])
def test_field_units_outside_the_enum_become_unknown(raw: str):
    """Satuan ini nyata dipakai di gudang tapi sengaja di luar enum.

    Kalau salah satunya diam-diam dipetakan ke enum lain, Modul 2 akan
    menghitung barang dengan satuan yang keliru.
    """
    assert normalize_unit(raw) == UnitNormalized.UNKNOWN


@pytest.mark.parametrize("raw", [None, "", "   ", "???", "12"])
def test_unreadable_units_are_unknown_not_an_error(raw):
    assert normalize_unit(raw) == UnitNormalized.UNKNOWN


def test_digits_do_not_confuse_the_mapping():
    assert normalize_unit("12 pcs") == UnitNormalized.PCS
    assert normalize_unit("5 Karton") == UnitNormalized.KARTON


def test_agrees_with_the_step_3_dataset_labels():
    """Normaliser runtime harus sepakat dengan peta yang melabeli dataset.

    ``vocab.py`` hanya ada di image dev, jadi engine tidak bisa mengimpornya.
    Test inilah yang menjaga keduanya tidak menyimpang diam-diam.
    """
    vocab = pytest.importorskip(
        "scripts.synthetic.vocab", reason="vocab generator hanya ada di image dev"
    )

    disagreements = {
        raw: (normalize_unit(raw), expected)
        for raw, expected in vocab.UNIT_MAP.items()
        if normalize_unit(raw) != expected
    }
    assert not disagreements, f"normalisasi runtime menyimpang dari label dataset: {disagreements}"
