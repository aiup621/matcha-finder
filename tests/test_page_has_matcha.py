import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import pipeline_smart as ps


def test_page_has_matcha_simple_html():
    html = "<html><body>Our Matcha Latte</body></html>"
    assert ps.page_has_matcha(html)
