import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from query_builder import build_query


def test_build_query_contains_intent_and_negatives():
    seed = {"city": "Seattle", "state": "WA", "keywords": "dessert"}
    q = build_query(seed)
    assert '-site:facebook.com' in q
    assert '-site:square.site' in q
    assert '"matcha"' in q
    assert 'latte' in q or 'menu' in q  # intent terms
    assert 'Seattle' in q and 'WA' in q


def test_build_query_dedup():
    seed = {"city": "Seattle", "state": "WA", "keywords": "Seattle"}
    q = build_query(seed)
    assert q.count('Seattle') == 1
