"""Integration of Custom Search API and Google Sheets API.

This module reads rows from a Google Sheet, searches for the homepage of each
entry using the Custom Search API and then extracts contact information from
the homepage using existing helper functions from ``update_contact_info``.
The results are written back to the sheet.

Usage example::

    python update_contact_info_api.py \
        --spreadsheet-id SPREADSHEET_ID \
        --range 'Sheet1!A:G' \
        --credentials service_account.json \
        --api-key YOUR_API_KEY \
        --cx SEARCH_ENGINE_ID

The sheet is expected to have the following structure:

================  ============================================================
Column           Meaning
================  ============================================================
A                Query string (e.g. store name or address)
B                Unused
C                Homepage URL (filled automatically if missing)
D                Instagram account URL
E                Contact e-mail address
F                Contact form URL
G                "なし" if none of the above could be found
================  ============================================================
"""

from __future__ import annotations

import argparse
import logging
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2 import service_account

import update_contact_info as uc

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def search_homepage(query: str, api_key: str, cx: str) -> Optional[str]:
    """Search for the homepage of *query* using Google Custom Search."""
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=cx, num=1).execute()
    items: Iterable[dict] | None = res.get("items")
    return items[0]["link"] if items else None


def _build_sheet_service(credentials_file: str):
    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def read_rows(spreadsheet_id: str, range_: str, credentials_file: str) -> List[List[str]]:
    """Return rows from the given sheet range."""
    service = _build_sheet_service(credentials_file)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_)
        .execute()
    )
    return result.get("values", [])


def update_rows(
    spreadsheet_id: str, range_: str, values: List[List[str]], credentials_file: str
) -> None:
    """Write values into the sheet."""
    service = _build_sheet_service(credentials_file)
    (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="RAW",
            body={"values": values},
        )
        .execute()
    )


def process_sheet(
    spreadsheet_id: str,
    range_: str,
    api_key: str,
    cx: str,
    credentials_file: str,
    start_row: int = 2,
    debug: bool = False,
) -> None:
    """Read rows from the sheet and update contact information.

    ``range_`` should encompass columns A through G. Processing stops when an
    empty value is encountered in column A.
    """
    if debug:
        logging.basicConfig(level=logging.INFO)

    rows = read_rows(spreadsheet_id, range_, credentials_file)

    for index, row in enumerate(rows[start_row - 1 :], start=start_row):
        if not row or not row[0]:
            break  # Stop at first empty row in column A
        query = row[0]
        homepage = row[2] if len(row) > 2 else ""
        if not homepage:
            homepage = search_homepage(query, api_key, cx)
        if not homepage:
            logging.warning("No homepage found for %s", query)
            continue
        try:
            resp = requests.get(homepage, timeout=uc.REQUEST_TIMEOUT)
        except requests.RequestException as exc:  # pragma: no cover - network
            logging.warning("Request failed for %s: %s", homepage, exc)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        insta = uc.find_instagram(soup, homepage) or ""
        email = uc.find_email(soup) or ""
        form = uc.find_contact_form(soup, homepage) or ""
        none_flag = "なし" if not any([insta, email, form]) else ""
        values = [[homepage, insta, email, form, none_flag]]
        update_range = f"C{index}:G{index}"
        update_rows(spreadsheet_id, update_range, values, credentials_file)
        logging.info(
            "Updated row %s - homepage %s", index, homepage
        )


def main() -> None:  # pragma: no cover - CLI wrapper
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--range", default="Sheet1!A:G")
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--cx", required=True, help="Custom search engine ID")
    parser.add_argument("--start-row", type=int, default=2)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    process_sheet(
        args.spreadsheet_id,
        args.range,
        args.api_key,
        args.cx,
        args.credentials,
        args.start_row,
        args.debug,
    )


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    main()
