import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from blocklist import is_blocked_domain
from crawler.query_builder import QueryBuilder


def test_blocklist_and_query_filter():
    patterns = ["facebook.com", "mapquest.com"]
    qb = QueryBuilder(blocklist=patterns)
    qs = qb.build_queries()
    assert any("-site:facebook.com" in q for q in qs)
    assert is_blocked_domain("http://facebook.com/page", patterns)
