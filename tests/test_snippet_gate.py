import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from crawler.snippet_gate import accepts


def test_near_matcha_latte():
    snippet = "Our cafe serves matcha latte and pastries"
    assert accepts("http://example.com", snippet)


def test_far_tokens_rejected():
    snippet = "matcha " + ("x" * 60) + " latte specials"
    assert not accepts("http://example.com", snippet)


def test_menu_url_with_matcha():
    snippet = "Best matcha drinks in town"
    assert accepts("http://example.com/menu", snippet)
