"""Test penjodohan baris.

Penjodohan yang salah membuat seluruh angka evaluasi ikut salah tanpa ada yang
gagal — jenis kekeliruan yang paling mahal, karena hasilnya tetap terlihat
meyakinkan.
"""

from dataclasses import dataclass

from scripts.evaluation.matching import match_items, normalize_name, similarity


@dataclass
class Row:
    item_name: str


def rows(*names: str) -> list[Row]:
    return [Row(name) for name in names]


def test_identical_lists_pair_one_to_one():
    truth = rows("Susu UHT 250ml", "Kecap Bango 600ml", "Beras Ramos 5kg")
    result = match_items(truth, rows("Susu UHT 250ml", "Kecap Bango 600ml", "Beras Ramos 5kg"))

    assert len(result.matches) == 3
    assert result.exact_matches == 3
    assert result.recall == 1.0
    assert result.precision == 1.0
    assert result.missed_truth == []
    assert result.spurious_predicted == []


def test_order_does_not_matter():
    """Model tidak wajib mengembalikan baris dengan urutan yang sama."""
    truth = rows("Susu UHT 250ml", "Kecap Bango 600ml")
    result = match_items(truth, rows("Kecap Bango 600ml", "Susu UHT 250ml"))

    assert result.recall == 1.0
    pairs = {(m.truth_index, m.predicted_index) for m in result.matches}
    assert pairs == {(0, 1), (1, 0)}


def test_small_spelling_differences_still_match_but_not_as_exact():
    """Inilah yang membedakan 'salah baca' dari 'beda penulisan'."""
    result = match_items(rows("Susu UHT Ultra 250ml"), rows("Susu UHT Ultra 250 ml"))

    assert len(result.matches) == 1
    assert result.matches[0].exact is False
    assert result.recall == 1.0


def test_case_and_punctuation_are_ignored_for_exactness():
    result = match_items(rows("Minyak Goreng Bimoli 1L"), rows("minyak goreng bimoli 1l"))

    assert result.matches[0].exact is True


def test_missing_row_counts_against_recall_only():
    truth = rows("Susu UHT 250ml", "Kecap Bango 600ml")
    result = match_items(truth, rows("Susu UHT 250ml"))

    assert result.recall == 0.5
    assert result.precision == 1.0  # yang dikembalikan memang benar ada
    assert result.missed_truth == [1]


def test_invented_row_counts_against_precision_only():
    truth = rows("Susu UHT 250ml")
    result = match_items(truth, rows("Susu UHT 250ml", "Barang Karangan"))

    assert result.recall == 1.0
    assert result.precision == 0.5
    assert result.spurious_predicted == [1]


def test_duplicate_names_do_not_double_match():
    """Dua baris prediksi bernama sama tidak boleh memenuhi satu baris truth dua kali."""
    result = match_items(rows("Susu UHT 250ml"), rows("Susu UHT 250ml", "Susu UHT 250ml"))

    assert len(result.matches) == 1
    assert result.spurious_predicted == [1]


def test_two_truth_rows_with_the_same_name_each_need_their_own_prediction():
    truth = rows("Susu UHT 250ml", "Susu UHT 250ml")
    result = match_items(truth, rows("Susu UHT 250ml"))

    assert len(result.matches) == 1
    assert result.missed_truth == [1]


def test_completely_different_names_do_not_match():
    result = match_items(rows("Susu UHT 250ml"), rows("Semen Tiga Roda 40kg"))

    assert result.matches == []
    assert result.recall == 0.0
    assert result.precision == 0.0


def test_empty_prediction_gives_zero_recall_but_no_crash():
    result = match_items(rows("Susu UHT 250ml"), [])

    assert result.recall == 0.0
    assert result.precision == 1.0  # tidak ada yang dikarang
    assert result.missed_truth == [0]


def test_both_empty_is_perfect_not_an_error():
    result = match_items([], [])

    assert result.recall == 1.0
    assert result.precision == 1.0


def test_matches_are_returned_in_truth_order():
    truth = rows("A satu", "B dua", "C tiga")
    result = match_items(truth, rows("C tiga", "A satu", "B dua"))

    assert [m.truth_index for m in result.matches] == [0, 1, 2]


def test_normalize_and_similarity_basics():
    assert normalize_name("  Susu   UHT, 250ml! ") == "susu uht 250ml"
    assert normalize_name(None) == ""
    assert similarity("Susu UHT", "susu uht") == 1.0
    assert similarity("Susu UHT", None) == 0.0
    assert similarity(None, None) == 1.0
