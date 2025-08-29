import sys, pathlib, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from crawler.query_builder import QueryBuilder


def test_queries_ascii_and_blocklist():
    os.environ["FORCE_ENGLISH_QUERIES"] = "1"
    os.environ["EXCLUDE_DOMAINS"] = "facebook.com"
    os.environ["EXCLUDE_DOMAINS_EXTRA"] = "instagram.com"
    qb = QueryBuilder(blocklist=["mapquest.com"])
    queries = qb.build_queries()
    assert 8 <= len(queries) <= 12
    assert any("-site:facebook.com" in q for q in queries)
    assert any("-site:instagram.com" in q for q in queries)
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


def test_query_builder_ascii_only():
    os.environ["FORCE_ENGLISH_QUERIES"] = "1"
    qb = QueryBuilder(city_seeds=["東京", "Seattle"])
    # non ASCII seed should be dropped
    assert qb.cities == ["Seattle"]
    for q in qb.build_queries():
        q.encode("ascii")


def test_query_templates_examples():
    templates = [
        "independent matcha cafe {city} contact",
        "matcha latte cafe {city} website",
        '"tea house" matcha {city} "contact us"',
        '"Japanese tea" cafe {city} contact',
        '"ceremonial matcha" cafe {city} contact',
        '"matcha bar" {city} contact',
        '"green tea latte" cafe {city} site',
        '"best matcha" {city} "contact" -amazon -reddit -pinterest',
    ]
    for t in templates:
        t.format(city="Austin").encode("ascii")
