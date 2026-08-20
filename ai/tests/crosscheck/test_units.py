"""Satuan mana yang sebanding dengan hitungan kamera.

Ini keputusan paling menentukan di Modul 3: salah memasukkan satu satuan ke
daftar yang dihitung akan melahirkan selisih palsu di setiap kiriman yang memuat
satuan itu.
"""

import pytest

from app.modules.crosscheck.schemas import ExclusionReason
from app.modules.crosscheck.service import CARDBOARD_UNITS, classify_unit
from app.modules.document.schemas import UnitNormalized

U = UnitNormalized


@pytest.mark.parametrize("unit", [U.KARTON, U.BOX, U.KOLI])
def test_cardboard_units_are_counted(unit):
    assert classify_unit(unit) is None


@pytest.mark.parametrize(
    ("unit", "reason"),
    [
        (U.KG, ExclusionReason.UNIT_IS_WEIGHT),
        (U.UNKNOWN, ExclusionReason.UNIT_UNKNOWN),
        (U.PCS, ExclusionReason.UNIT_NOT_CARDBOARD),
        (U.LUSIN, ExclusionReason.UNIT_NOT_CARDBOARD),
        (U.ROLL, ExclusionReason.UNIT_NOT_CARDBOARD),
        (U.SAK, ExclusionReason.UNIT_NOT_CARDBOARD),
    ],
)
def test_non_cardboard_units_are_excluded_with_a_reason(unit, reason):
    assert classify_unit(unit) is reason


def test_sack_and_roll_are_countable_objects_but_still_excluded():
    """Karung dan gulungan bisa dicacah manusia, tetapi model tidak dilatih
    mengenalinya. Menjumlahkannya akan menuduh kiriman yang sebenarnya utuh."""
    assert classify_unit(U.SAK) is ExclusionReason.UNIT_NOT_CARDBOARD
    assert classify_unit(U.ROLL) is ExclusionReason.UNIT_NOT_CARDBOARD


def test_every_unit_in_the_enum_is_classified():
    """Satuan baru di Modul 1 tidak boleh diam-diam jatuh ke perlakuan default."""
    for unit in UnitNormalized:
        result = classify_unit(unit)
        assert result is None or isinstance(result, ExclusionReason)
        assert (result is None) == (unit in CARDBOARD_UNITS)
