import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from contact_extractors import extract_contact_endpoints


def test_extract_contact_endpoints_basic():
    html = """
    <html><body>
    <a href="/contact-us">Contact Us</a>
    <a href="mailto:info@example.com">Email</a>
    <form action="/send"><input/></form>
    <iframe src="https://formspree.io/f/abc"></iframe>
    <a href="tel:+1-555-123-4567">Call</a>
    </body></html>
    """
    data = extract_contact_endpoints(html, "https://example.com")
    assert "https://example.com/contact-us" in data["contact_pages"]
    assert "info@example.com" in data["emails"]
    assert "https://example.com/send" in data["form_urls"]
    assert any(p["provider"] == "formspree" for p in data["form_providers"])
    assert "+1-555-123-4567" in data["phones"]
