import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from smart_search import QueryBuilder


def test_rotation_changes_city():
    qb = QueryBuilder(rotate_threshold=2)
    first = qb.current_city()
    qb.record_skip()
    qb.record_skip()  # should trigger rotation
    second = qb.current_city()
    assert first != second
