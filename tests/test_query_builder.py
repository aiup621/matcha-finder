import sys, pathlib, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from crawler.query_builder import QueryBuilder, wrap_query, is_valid_domain


def test_queries_ascii_and_blocklist():
    os.environ["ENGLISH_ONLY"] = "1"
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
            "tea house",
            "artisan matcha",
            "new matcha cafe opening",
            "best matcha",
            "third wave cafe",
        ])
        if len(q) < 256:
            assert "-site:" in q


def test_query_builder_ascii_only():
    os.environ["ENGLISH_ONLY"] = "1"
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


def test_wrap_query_no_positive_site():
    q = wrap_query("matcha", ["betterbuzzcoffee.com"])
    assert "-site:betterbuzzcoffee.com" in q
    assert "site:betterbuzzcoffee.com" not in q.replace("-site:betterbuzzcoffee.com", "")


def test_is_valid_domain():
    assert is_valid_domain("gongchausa.com")
    assert not is_valid_domain("gong-cha")
