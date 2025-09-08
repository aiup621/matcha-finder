from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from email_extractors import decode_cfemail, extract_emails_from_html, pick_best


def _cf_encode(addr: str, key: int = 0x12) -> str:
    bs = bytes([key]) + bytes([ord(c) ^ key for c in addr])
    return ''.join(f'{b:02x}' for b in bs)


def test_cfemail_decode_roundtrip():
    addr = 'info@thegallerypei.ca'
    hexstr = _cf_encode(addr, 0x33)
    assert decode_cfemail(hexstr) == addr


def test_obfuscated_text():
    html = 'Contact: info (at) thegallerypei (dot) ca'
    got = extract_emails_from_html('https://example.com', html)
    assert 'info@thegallerypei.ca' in got


def test_jsonld_email():
    html = '''<script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization","email":"hello@example.com"}
    </script>'''
    got = extract_emails_from_html('https://example.com', html)
    assert 'hello@example.com' in got


def test_pick_best_prefers_sales():
    emails = {'info@example.com', 'wholesale@example.com'}
    assert pick_best(emails) == 'wholesale@example.com'
