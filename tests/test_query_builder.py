import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from crawler.query_builder import QueryBuilder


def test_queries_ascii_and_blocklist():
    qb = QueryBuilder(blocklist=["facebook.com", "mapquest.com"])
    queries = qb.build_queries()
    assert 8 <= len(queries) <= 12
    assert any("-site:facebook.com" in q for q in queries)
    for q in queries:
        q.encode("ascii")
        assert len(q) <= 256
        assert any(term in q for term in [
            "matcha latte",
            "matcha cafe",
            "matcha menu",
            "green tea latte",
            "ceremonial matcha",
        ])
        if len(q) < 256:
            assert "-site:" in q
