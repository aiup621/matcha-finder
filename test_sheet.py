import os
import time

import gspread
import pytest
from dotenv import load_dotenv


load_dotenv()


def test_append_row_to_sheet():
    """Append a simple healthcheck row to the Google Sheet.

    The test requires Google Sheets credentials. If they are not
    configured, the test is skipped so that the rest of the suite can
    run in environments without external access.
    """

    sheet_id = os.environ.get("SHEET_ID")
    ws_name = os.environ.get("GOOGLE_WORKSHEET_NAME", "raw")
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")

    if not sheet_id or not os.path.exists(sa_json):
        pytest.skip("Google Sheets credentials not configured")

    gc = gspread.service_account(filename=sa_json)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(ws_name)
    row = ["_healthcheck_", time.strftime("%Y-%m-%d %H:%M:%S")]
    ws.append_row(row)

    # If the above operations succeed without exception, the test passes.
    assert True

