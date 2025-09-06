from bs4 import BeautifulSoup
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


def test_process_sheet_row_range(tmp_path, monkeypatch):
    import openpyxl

    class DummyResponse:
        text = "<html></html>"

    def dummy_get(url, timeout):
        return DummyResponse()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.cell(row=2, column=3, value="http://a")
    ws.cell(row=3, column=3, value="http://b")
    file = tmp_path / "sample.xlsx"
    wb.save(file)

    monkeypatch.setattr(uc.requests, "get", dummy_get)
    uc.process_sheet(str(file), start_row=2, end_row=2, worksheet="Sheet")

    wb2 = openpyxl.load_workbook(file)
    ws2 = wb2.active
    assert ws2.cell(row=2, column=7).value == "なし"
    assert ws2.cell(row=3, column=7).value is None


def test_process_specific_worksheet(tmp_path, monkeypatch):
    import openpyxl

    class DummyResponse:
        text = "<html></html>"

    def dummy_get(url, timeout):
        return DummyResponse()

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Sheet1"
    ws1.cell(row=2, column=3, value="http://a")
    ws2 = wb.create_sheet("Sheet2")
    ws2.cell(row=2, column=3, value="http://b")
    file = tmp_path / "sample.xlsx"
    wb.save(file)

    monkeypatch.setattr(uc.requests, "get", dummy_get)
    uc.process_sheet(str(file), start_row=2, end_row=2, worksheet="Sheet2")

    wb2 = openpyxl.load_workbook(file)
    assert wb2["Sheet1"].cell(row=2, column=7).value is None
    assert wb2["Sheet2"].cell(row=2, column=7).value == "なし"
