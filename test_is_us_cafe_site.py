import sys, types

pdfminer_stub = types.ModuleType("pdfminer")
high_level_stub = types.ModuleType("pdfminer.high_level")
high_level_stub.extract_text = lambda *a, **k: ""
pdfminer_stub.high_level = high_level_stub
sys.modules.setdefault("pdfminer", pdfminer_stub)
sys.modules.setdefault("pdfminer.high_level", high_level_stub)

import light_extract


def test_state_with_menu(monkeypatch):
    monkeypatch.setattr(light_extract, "http_get", lambda *a, **k: None)
    html = "<html><body>local cafe menu CA</body></html>"
    assert light_extract.is_us_cafe_site("https://example.com", html)
