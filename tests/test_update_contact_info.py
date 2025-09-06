from bs4 import BeautifulSoup
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import update_contact_info as uc


def test_find_instagram():
    html = '<a href="https://www.instagram.com/test">IG</a>'
    soup = BeautifulSoup(html, "html.parser")
    assert uc.find_instagram(soup, "http://example.com") == "https://www.instagram.com/test"


def test_find_email_from_mailto():
    html = '<a href="mailto:info@example.com">mail</a>'
    soup = BeautifulSoup(html, "html.parser")
    assert uc.find_email(soup) == "info@example.com"


def test_find_email_from_mailto_case_insensitive():
    html = '<a href="MAILTO:INFO@EXAMPLE.COM?subject=test">mail</a>'
    soup = BeautifulSoup(html, "html.parser")
    assert uc.find_email(soup) == "INFO@EXAMPLE.COM"


def test_find_contact_form():
    html = '<a href="/contact">contact</a>'
    soup = BeautifulSoup(html, "html.parser")
    assert uc.find_contact_form(soup, "http://example.com") == "http://example.com/contact"
