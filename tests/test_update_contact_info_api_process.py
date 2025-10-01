import update_contact_info_api as api


class FakeRequest:
    def __init__(self, func):
        self._func = func

    def execute(self):
        return self._func()


class FakeValues:
    def __init__(self, service):
        self._service = service

    def get(self, spreadsheetId, range, **_):
        self._service.requested_ranges.append(range)
        return FakeRequest(lambda: {"values": self._service.rows})

    def update(self, spreadsheetId, range, valueInputOption, body):
        def _execute():
            self._service.updates.append({
                "range": range,
                "values": body.get("values", []),
            })
            return {}

        return FakeRequest(_execute)

    def batchUpdate(self, spreadsheetId, body):
        def _execute():
            for item in body.get("data", []):
                self._service.updates.append(
                    {
                        "range": item.get("range"),
                        "values": item.get("values", []),
                    }
                )
            return {}

        return FakeRequest(_execute)


class FakeSpreadsheets:
    def __init__(self, service):
        self._service = service

    def values(self):
        return FakeValues(self._service)

    def get(self, spreadsheetId, fields):
        return FakeRequest(
            lambda: {
                "sheets": [
                    {
                        "properties": {
                            "sheetId": self._service.sheet_id,
                            "title": self._service.worksheet,
                        }
                    }
                ]
            }
        )


class FakeService:
    def __init__(self, rows, worksheet="Sheet"):
        self.rows = rows
        self.worksheet = worksheet
        self.sheet_id = 99
        self.updates = []
        self.requested_ranges = []

    def spreadsheets(self):
        return FakeSpreadsheets(self)


def test_process_sheet_deletes_error_rows(monkeypatch):
    rows = [
        ["data", "", "https://bad.example"],
        ["data", "", "https://ok.example"],
    ]
    service = FakeService(rows)

    monkeypatch.setattr(api, "_build_sheet_service", lambda credentials_file: service)
    monkeypatch.setattr(
        api,
        "_fetch_page",
        lambda url, timeout, verify, **_: None if "bad" in url else "<html></html>",
    )
    monkeypatch.setattr(api, "find_instagram", lambda soup, url: "")
    monkeypatch.setattr(api, "crawl_site_for_email", lambda url, timeout, verify: "")
    monkeypatch.setattr(
        api, "find_contact_form", lambda soup, url, timeout, verify: ""
    )
    monkeypatch.setattr(api, "get_sheet_id", lambda service_obj, spreadsheet_id, title: 99)

    deleted = {}

    def fake_delete_rows(service_obj, spreadsheet_id, sheet_id, row_indices):
        deleted["indices"] = list(row_indices)

    monkeypatch.setattr(api, "delete_rows", fake_delete_rows)
    monkeypatch.setenv("CLEANUP_DUPLICATE_EMAIL_ROWS", "false")
    monkeypatch.setenv("DELETE_ERROR_ROWS", "true")
    monkeypatch.delenv("DRY_RUN", raising=False)

    result = api.process_sheet(
        "spreadsheet",
        "Sheet",
        start_row=2,
        max_rows=2,
        timeout=1.0,
        verify_ssl=True,
        credentials_file="creds.json",
    )

    assert result == 2
    assert service.updates == [
        {"range": "Sheet!D2:G2", "values": [["", "", "", "エラー"]]},
        {"range": "Sheet!D3:G3", "values": [["", "", "", "なし"]]},
    ]
    assert deleted["indices"] == [1]


def test_error_row_deletion_adjusts_written_rows_for_cleanup(monkeypatch):
    rows = [
        ["data", "", "https://bad.example"],
        ["data", "", "https://ok.example"],
    ]
    service = FakeService(rows)

    monkeypatch.setattr(api, "_build_sheet_service", lambda credentials_file: service)
    monkeypatch.setattr(
        api,
        "_fetch_page",
        lambda url, timeout, verify, **_: None if "bad" in url else "<html></html>",
    )
    monkeypatch.setattr(api, "find_instagram", lambda soup, url: "")
    monkeypatch.setattr(api, "crawl_site_for_email", lambda url, timeout, verify: "")
    monkeypatch.setattr(
        api, "find_contact_form", lambda soup, url, timeout, verify: ""
    )
    monkeypatch.setattr(api, "get_sheet_id", lambda service_obj, spreadsheet_id, title: 99)

    captured = {}

    def fake_cleanup_duplicates_written_only(
        *,
        service,
        spreadsheet_id,
        title,
        email_col_letter,
        header_rows,
        written_rows,
        dry_run,
    ):
        captured["written_rows"] = list(written_rows)
        return 0

    monkeypatch.setattr(api, "cleanup_duplicates_written_only", fake_cleanup_duplicates_written_only)

    deleted = {}

    def fake_delete_rows(service_obj, spreadsheet_id, sheet_id, row_indices):
        deleted["indices"] = list(row_indices)

    monkeypatch.setattr(api, "delete_rows", fake_delete_rows)

    monkeypatch.setenv("CLEANUP_DUPLICATE_EMAIL_ROWS", "true")
    monkeypatch.setenv("DELETE_ERROR_ROWS", "true")
    monkeypatch.delenv("DRY_RUN", raising=False)

    result = api.process_sheet(
        "spreadsheet",
        "Sheet",
        start_row=2,
        max_rows=2,
        timeout=1.0,
        verify_ssl=True,
        credentials_file="creds.json",
    )

    assert result == 2
    assert deleted["indices"] == [1]
    assert captured["written_rows"] == [2]
