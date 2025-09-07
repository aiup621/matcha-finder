"""Update contact information directly on a Google Sheet via the Sheets API.

The sheet is expected to have the following columns:

================  ============================================================
Column           Meaning
================  ============================================================
A                Arbitrary label used to detect the end of data
B                Unused
C                Homepage URL (input)
D                Instagram URL (output)
E                E-mail address (output)
F                Contact form URL (output)
G                Status column – "なし" if nothing was found, "エラー" on errors
================  ============================================================

Only rows starting from ``--start-row`` are processed.  Processing stops when
column A is blank or when ``--max-rows`` rows have been handled.

Example usage::

    python update_contact_info_api.py \
        --spreadsheet-id <ID> \
        --worksheet "抹茶営業リスト（カフェ）" \
        --start-row 2
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Optional

import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2 import service_account

from update_contact_info import (
    find_contact_form,
    find_email,
    find_instagram,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _build_sheet_service(credentials_file: str) -> "Resource":
    """Return an authorised Sheets API client."""

    if not os.path.exists(credentials_file):
        raise SystemExit(f"Credentials file not found: {credentials_file}")
    try:
        with open(credentials_file, "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid service account JSON: {exc}")

    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def _fetch_page(url: str, timeout: float, verify: bool) -> Optional[str]:
    """Return the page content for ``url`` with simple retry handling."""

    for _ in range(3):  # at least two retries
        try:
            res = requests.get(url, timeout=timeout, verify=verify)
            res.raise_for_status()
            return res.text
        except requests.RequestException:
            continue
    return None


def process_sheet(
    spreadsheet_id: str,
    worksheet: str,
    start_row: int,
    max_rows: Optional[int],
    timeout: float,
    verify_ssl: bool,
    credentials_file: str,
) -> int:
    """Process rows on the sheet and return the number of updated rows."""

    service = _build_sheet_service(credentials_file)

    end_row = "" if max_rows is None else str(start_row + max_rows - 1)
    read_range = f"{worksheet}!A{start_row}:G{end_row}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=read_range)
        .execute()
    )
    rows = result.get("values", [])

    updated = 0
    for offset, row in enumerate(rows):
        row_index = start_row + offset
        if not row or not row[0]:
            break  # Stop when column A is blank

        url = row[2].strip() if len(row) > 2 and isinstance(row[2], str) else ""
        insta = email = form = ""
        status = ""

        if not url:
            status = "なし"
        elif not url.lower().startswith(("http://", "https://")):
            status = "エラー"
        else:
            content = _fetch_page(url, timeout=timeout, verify=verify_ssl)
            if content is None:
                status = "エラー"
            else:
                soup = BeautifulSoup(content, "html.parser")
                insta = find_instagram(soup, url) or ""
                email = find_email(soup) or ""
                form = find_contact_form(soup, url) or ""
                if not any([insta, email, form]):
                    status = "なし"

        values = [[insta, email, form, status]]
        update_range = f"{worksheet}!D{row_index}:G{row_index}"
        (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=update_range,
                valueInputOption="RAW",
                body={"values": values},
            )
            .execute()
        )
        logging.info(
            "Processed row %s: IG=%s, email=%s, form=%s, status=%s",
            row_index,
            insta or "-",
            email or "-",
            form or "-",
            status or "-",
        )
        updated += 1
        if max_rows is not None and updated >= max_rows:
            break

    logging.info("Updated %s rows", updated)
    return updated


def main() -> None:  # pragma: no cover - CLI entry point
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--worksheet", default="抹茶営業リスト（カフェ）")
    parser.add_argument("--start-row", type=int, default=2)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--verify-ssl", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--credentials",
        default="sa.json",
        help="Path to service account JSON file",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.spreadsheet_id.strip():
        parser.error("--spreadsheet-id must not be empty")

    process_sheet(
        spreadsheet_id=args.spreadsheet_id,
        worksheet=args.worksheet,
        start_row=args.start_row,
        max_rows=args.max_rows,
        timeout=args.timeout,
        verify_ssl=args.verify_ssl,
        credentials_file=args.credentials,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

