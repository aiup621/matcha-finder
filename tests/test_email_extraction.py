from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect_emails as ce


def _resp(url, pages):
    class Resp:
        def __init__(self, url):
            self.url = url
            self.status_code = 200
            self.text = pages.get(url, "")
            self.content = self.text.encode("utf-8")

        def raise_for_status(self):
            pass

    return Resp(url)


def test_js_mailto_in_script(monkeypatch):
    pages = {"http://example.com": "<script>window.location='mailto:info@example.com'</script>"}

    def fake_get(url, timeout=5, verify=True, headers=None):
        return _resp(url, pages)

    monkeypatch.setattr(ce.requests, "get", fake_get)
    info = ce.collect_emails("http://example.com")
    assert info["email"] == "info@example.com"
    assert info["surface"] == "script"


def test_data_user_domain(monkeypatch):
    pages = {"http://example.com": '<div data-user="info" data-domain="example.com"></div>'}

    def fake_get(url, timeout=5, verify=True, headers=None):
        return _resp(url, pages)

    monkeypatch.setattr(ce.requests, "get", fake_get)
    info = ce.collect_emails("http://example.com")
    assert info["email"] == "info@example.com"
    assert info["surface"] == "data-attr"


def test_obfuscated_at_dot(monkeypatch):
    pages = {"http://example.com": "info [at] example [dot] com"}

    def fake_get(url, timeout=5, verify=True, headers=None):
        return _resp(url, pages)

    monkeypatch.setattr(ce.requests, "get", fake_get)
    info = ce.collect_emails("http://example.com")
    assert info["email"] == "info@example.com"
    assert info["surface"] == "obfuscated"


def test_fallback_contact_page(monkeypatch):
    pages = {
        "http://example.com": "no email",
        "http://example.com/contact": '<a href="mailto:info@example.com">c</a>',
    }

    def fake_get(url, timeout=5, verify=True, headers=None):
        return _resp(url, pages)

    monkeypatch.setattr(ce.requests, "get", fake_get)
    info = ce.collect_emails("http://example.com")
    assert info["email"] == "info@example.com"
    assert info["page"] == "/contact"


def test_onclick_mailto(monkeypatch):
    pages = {
        "http://example.com": "<button onclick=\"window.location='mailto:firstandlastcoffee@gmail.com'\">Email</button>"
    }

    def fake_get(url, timeout=5, verify=True, headers=None):
        return _resp(url, pages)

    monkeypatch.setattr(ce.requests, "get", fake_get)
    info = ce.collect_emails("http://example.com")
    assert info["email"] == "firstandlastcoffee@gmail.com"
    assert info["surface"] == "script"
