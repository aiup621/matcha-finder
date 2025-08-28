import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from smart_search import QueryBuilder


def test_exclude_sites_and_trim():
    qb = QueryBuilder()
    q = qb.build()
    for site in qb.exclude_sites:
        assert f"-site:{site}" in q
    # Make query artificially long
    qb.exclude_sites = [f"example{i}.com" for i in range(50)]
    q2 = qb.build()
    assert len(q2) <= 250
