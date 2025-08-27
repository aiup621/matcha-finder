from verify_matcha import _has_matcha_text
import types, sys

pdfminer = types.ModuleType("pdfminer")
high_level = types.ModuleType("high_level")
high_level.extract_text = lambda *a, **k: ""
pdfminer.high_level = high_level
sys.modules["pdfminer"] = pdfminer
sys.modules["pdfminer.high_level"] = high_level

import light_extract


def test_direct_matcha_word():
    assert _has_matcha_text("Try our Matcha latte today!")


def test_secondary_keyword_without_matcha():
    text = "We serve ceremonial green tea desserts"
    assert _has_matcha_text(text)


def test_negative_word_only():
    assert not _has_matcha_text("Houjicha and sencha available")


def test_is_us_cafe_from_address(monkeypatch):
    html = """<html><body><p>Cozy cafe</p><address>123 Road, Seattle, WA</address></body></html>"""
    monkeypatch.setattr(light_extract, "geocode_city_state", lambda c, s: True)
    assert light_extract.is_us_cafe_site("https://example.com", html)


def test_is_us_cafe_from_postaladdress(monkeypatch):
    html = (
        """
<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Cafe","address":{"@type":"PostalAddress","addressLocality":"Austin","addressRegion":"TX"}}
</script></head><body>Tea House</body></html>
"""
    )
    monkeypatch.setattr(light_extract, "geocode_city_state", lambda c, s: True)
    assert light_extract.is_us_cafe_site("https://example.com", html)
