from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sheets_cleanup import _compress_consecutive_indices


def test_compress_descending_ranges():
    indices = [10, 9, 7, 6, 2]
    assert _compress_consecutive_indices(indices) == [(9, 11), (6, 8), (2, 3)]


def test_compress_singletons_and_duplicates():
    indices = [5, 5, 4, 1]
    # duplicates should not affect the grouping once sorted and deduplicated implicitly
    assert _compress_consecutive_indices(indices) == [(4, 6), (1, 2)]


def test_empty_indices():
    assert _compress_consecutive_indices([]) == []
