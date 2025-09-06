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
    ws.title = "Sheet"
    ws.cell(row=2, column=1, value="ok")
    ws.cell(row=2, column=3, value="http://a")
    ws.cell(row=3, column=3, value="http://b")
    file = tmp_path / "sample.xlsx"
    wb.save(file)

    monkeypatch.setattr(uc.requests, "get", dummy_get)
    uc.process_sheet(str(file), start_row=2, end_row=2, worksheet="Sheet")

    wb2 = openpyxl.load_workbook(file)
    ws2 = wb2["Sheet"]
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
    ws1.cell(row=2, column=1, value="ok")
    ws1.cell(row=2, column=3, value="http://a")
    ws2 = wb.create_sheet("Sheet2")
    ws2.cell(row=2, column=1, value="ok")
    ws2.cell(row=2, column=3, value="http://b")
    file = tmp_path / "sample.xlsx"
    wb.save(file)

    monkeypatch.setattr(uc.requests, "get", dummy_get)
    uc.process_sheet(str(file), start_row=2, end_row=2, worksheet="Sheet2")

    wb2 = openpyxl.load_workbook(file)
    assert wb2["Sheet1"].cell(row=2, column=7).value is None
    assert wb2["Sheet2"].cell(row=2, column=7).value == "なし"


def test_stop_on_blank_column_a(tmp_path, monkeypatch):
    import openpyxl

    class DummyResponse:
        text = "<html></html>"

    def dummy_get(url, timeout):
        return DummyResponse()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.cell(row=2, column=1, value="ok")
    ws.cell(row=2, column=3, value="http://a")
    ws.cell(row=3, column=3, value="http://b")  # A3 is blank
    ws.cell(row=4, column=1, value="ok")
    ws.cell(row=4, column=3, value="http://c")
    file = tmp_path / "sample.xlsx"
    wb.save(file)

    monkeypatch.setattr(uc.requests, "get", dummy_get)
    uc.process_sheet(str(file), start_row=2, worksheet="Sheet")

    wb2 = openpyxl.load_workbook(file)
    ws2 = wb2["Sheet"]
    assert ws2.cell(row=2, column=7).value == "なし"
    assert ws2.cell(row=3, column=7).value is None
    assert ws2.cell(row=4, column=7).value is None


def test_skip_invalid_url(tmp_path, monkeypatch):
    import openpyxl

    calls = []

    def dummy_get(url, timeout):
        calls.append(url)
        return None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.cell(row=2, column=1, value="ok")
    ws.cell(row=2, column=3, value="not a url")
    file = tmp_path / "sample.xlsx"
    wb.save(file)

    monkeypatch.setattr(uc.requests, "get", dummy_get)
    uc.process_sheet(str(file), start_row=2, end_row=2, worksheet="Sheet")

    assert calls == []
    wb2 = openpyxl.load_workbook(file)
    ws2 = wb2["Sheet"]
    assert ws2.cell(row=2, column=7).value is None


def test_process_sheet_from_url(tmp_path, monkeypatch):
    import io
    import openpyxl

    # Create an in-memory workbook to be served over a faux HTTP request.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.cell(row=2, column=1, value="ok")
    ws.cell(row=2, column=3, value="http://page")
    buf = io.BytesIO()
    wb.save(buf)
    content = buf.getvalue()

    class WorkbookResponse:
        def __init__(self, data):
            self.content = data

        def raise_for_status(self):
            pass

    class PageResponse:
        text = "<html></html>"

    def fake_get(url, timeout=10):
        return WorkbookResponse(content) if url == "http://sheet" else PageResponse()

    monkeypatch.setattr(uc.requests, "get", fake_get)
    monkeypatch.chdir(tmp_path)
    uc.process_sheet("http://sheet", start_row=2, end_row=2, worksheet="Sheet")

    wb2 = openpyxl.load_workbook(tmp_path / "downloaded.xlsx")
    ws2 = wb2["Sheet"]
    assert ws2.cell(row=2, column=7).value == "なし"


def test_google_sheet_link_is_transformed(monkeypatch, tmp_path):
    import io
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.cell(row=2, column=1, value="ok")
    ws.cell(row=2, column=3, value="http://page")
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()

    class WorkbookResponse:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    class PageResponse:
        text = "<html></html>"

    def fake_get(url, timeout=10):
        if url.startswith(
            "https://docs.google.com/spreadsheets/d/FILEID/export?format=xlsx&gid=0"
        ):
            return WorkbookResponse(data)
        if url == "http://page":
            return PageResponse()
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(uc.requests, "get", fake_get)
    monkeypatch.chdir(tmp_path)
    uc.process_sheet(
        "https://docs.google.com/spreadsheets/d/FILEID/edit?gid=0#gid=0",
        start_row=2,
        end_row=2,
        worksheet="Sheet",
    )

    wb2 = openpyxl.load_workbook(tmp_path / "downloaded.xlsx")
    ws2 = wb2["Sheet"]
    assert ws2.cell(row=2, column=7).value == "なし"
