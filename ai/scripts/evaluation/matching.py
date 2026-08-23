"""Menjodohkan baris barang hasil model dengan baris ground truth.

Tanpa penjodohan yang benar, seluruh angka evaluasi ikut salah. Model tidak
wajib mengembalikan baris dalam urutan yang sama, boleh melewatkan baris, dan
boleh mengarang baris — ketiganya harus terbaca sebagai hal berbeda.

Nama barang dipakai sebagai kunci karena itulah satu-satunya field yang cukup
khas. Jumlah tidak bisa jadi kunci: justru jumlah yang sedang diuji.

Kecocokan persis dan kecocokan mirip dilaporkan terpisah. Selisih keduanya
adalah "model membacanya, hanya menuliskannya sedikit berbeda" — beda besar
dengan "model tidak menemukannya sama sekali".
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Protocol

# Di bawah ini dianggap bukan baris yang sama. Dipilih longgar supaya beda
# spasi/tanda baca masih terjodoh, tetapi cukup ketat supaya dua produk
# berbeda tidak tertukar.
DEFAULT_THRESHOLD = 0.80

_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")


class HasItemName(Protocol):
    item_name: str


@dataclass(frozen=True)
class ItemMatch:
    truth_index: int
    predicted_index: int
    similarity: float
    exact: bool
    by_name: bool = True  # False = terjodoh lewat jumlah+satuan, namanya meleset


@dataclass(frozen=True)
class MatchResult:
    matches: list[ItemMatch]
    missed_truth: list[int]  # baris ground truth yang tidak ditemukan model
    spurious_predicted: list[int]  # baris yang dikarang model

    @property
    def recall(self) -> float:
        total = len(self.matches) + len(self.missed_truth)
        return len(self.matches) / total if total else 1.0

    @property
    def precision(self) -> float:
        total = len(self.matches) + len(self.spurious_predicted)
        return len(self.matches) / total if total else 1.0

    @property
    def exact_matches(self) -> int:
        return sum(1 for match in self.matches if match.exact)

    @property
    def name_matches(self) -> int:
        """Baris yang ketemu lewat namanya — artinya namanya memang terbaca."""
        return sum(1 for match in self.matches if match.by_name)

    @property
    def misnamed_matches(self) -> int:
        """Baris yang ada di dokumen dan angkanya benar, tapi namanya salah."""
        return sum(1 for match in self.matches if not match.by_name)


def normalize_name(name: str | None) -> str:
    """Buang tanda baca dan rapikan spasi; kapitalisasi diabaikan."""
    if not name:
        return ""
    cleaned = _PUNCT.sub(" ", name.lower())
    return _SPACE.sub(" ", cleaned).strip()


def similarity(left: str | None, right: str | None) -> float:
    a, b = normalize_name(left), normalize_name(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def match_items(
    truth: Sequence[HasItemName],
    predicted: Sequence[HasItemName],
    threshold: float = DEFAULT_THRESHOLD,
) -> MatchResult:
    """Jodohkan serakah dari pasangan paling mirip.

    Serakah, bukan optimal global: pada tabel surat jalan nama barang sangat
    berbeda satu sama lain, jadi pasangan terbaik hampir selalu jelas, dan
    hasilnya jauh lebih mudah dijelaskan saat angkanya dipertanyakan.

    Setiap indeks hanya boleh terpakai sekali, sehingga dua baris dengan nama
    identik tidak bisa dijodohkan ke baris ground truth yang sama.
    """
    candidates: list[tuple[float, int, int]] = []
    for t_index, t_item in enumerate(truth):
        for p_index, p_item in enumerate(predicted):
            score = similarity(t_item.item_name, p_item.item_name)
            if score >= threshold:
                candidates.append((score, t_index, p_index))

    # Skor menurun; indeks menaik supaya hasilnya deterministik saat skor seri.
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))

    matches: list[ItemMatch] = []
    used_truth: set[int] = set()
    used_predicted: set[int] = set()

    for score, t_index, p_index in candidates:
        if t_index in used_truth or p_index in used_predicted:
            continue
        used_truth.add(t_index)
        used_predicted.add(p_index)
        matches.append(
            ItemMatch(
                truth_index=t_index,
                predicted_index=p_index,
                similarity=score,
                exact=normalize_name(truth[t_index].item_name)
                == normalize_name(predicted[p_index].item_name),
            )
        )

    _match_by_quantity_and_unit(truth, predicted, matches, used_truth, used_predicted)

    matches.sort(key=lambda m: m.truth_index)

    return MatchResult(
        matches=matches,
        missed_truth=[i for i in range(len(truth)) if i not in used_truth],
        spurious_predicted=[i for i in range(len(predicted)) if i not in used_predicted],
    )


def _identity(item: object) -> tuple | None:
    """Kunci cadangan: jumlah + satuan apa adanya."""
    quantity = getattr(item, "quantity", None)
    if quantity is None:
        return None
    unit = getattr(item, "unit_raw", "") or ""
    return (quantity, unit.strip().casefold())


def _match_by_quantity_and_unit(
    truth: Sequence[HasItemName],
    predicted: Sequence[HasItemName],
    matches: list[ItemMatch],
    used_truth: set[int],
    used_predicted: set[int],
) -> None:
    """Sapuan kedua untuk baris yang namanya meleset tapi angkanya benar.

    Tanpa ini, model yang menulis kode barang ke kolom nama terbaca seolah-olah
    "barisnya tidak ketemu" — padahal barisnya ada dan jumlahnya benar. Dua
    kegagalan itu butuh perbaikan yang sama sekali berbeda, jadi tidak boleh
    dilaporkan sebagai satu angka.

    Hanya pasangan yang **saling tunggal** yang diterima: kalau ada dua baris
    dengan jumlah dan satuan sama, tidak ada cara jujur memilih, jadi keduanya
    dibiarkan tidak terjodoh daripada ditebak.
    """
    free_truth = [i for i in range(len(truth)) if i not in used_truth]
    free_predicted = [i for i in range(len(predicted)) if i not in used_predicted]

    for t_index in free_truth:
        key = _identity(truth[t_index])
        if key is None:
            continue

        candidates = [
            p_index
            for p_index in free_predicted
            if p_index not in used_predicted and _identity(predicted[p_index]) == key
        ]
        if len(candidates) != 1:
            continue

        # Sisi sebaliknya juga harus tunggal, supaya tidak ada tebakan tersembunyi.
        rivals = [
            other
            for other in free_truth
            if other not in used_truth and _identity(truth[other]) == key
        ]
        if len(rivals) != 1:
            continue

        p_index = candidates[0]
        used_truth.add(t_index)
        used_predicted.add(p_index)
        matches.append(
            ItemMatch(
                truth_index=t_index,
                predicted_index=p_index,
                similarity=similarity(truth[t_index].item_name, predicted[p_index].item_name),
                exact=False,
                by_name=False,
            )
        )
