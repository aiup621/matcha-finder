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


def test_process_sheet_updates_action_start_row(tmp_path, monkeypatch):
    import openpyxl

    # Prepare a workbook with an Action header specifying the start row
    path = tmp_path / "sheet.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Action"
    ws["B1"] = 3
    ws.cell(row=3, column=3).value = "http://example.com"
    wb.save(path)

    class DummyResp:
        text = '<a href="mailto:test@example.com">mail</a>'

    def fake_get(url, timeout=10):
        return DummyResp()

    monkeypatch.setattr(uc.requests, "get", fake_get)

    uc.process_sheet(path)

    wb2 = openpyxl.load_workbook(path)
    ws2 = wb2.active
    # After processing row 3, B1 should point to the next row (4)
    assert ws2["B1"].value == 4
    # Email extracted from the dummy page is written back to the sheet
    assert ws2.cell(row=3, column=5).value == "test@example.com"
