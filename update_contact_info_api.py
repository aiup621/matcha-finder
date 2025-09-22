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
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from update_contact_info import (
    find_contact_form,
    crawl_site_for_email,
    find_instagram,
)
from sheets_cleanup import (
    cleanup_duplicates_written_only,
    delete_rows,
    find_rows_by_programmatic_duplicates,
    find_rows_highlighted_as_duplicates,
    get_sheet_id,
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
    """Return the page content for ``url`` with retry handling."""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    for _ in range(3):
        try:
            res = requests.get(url, timeout=timeout, verify=verify, headers=headers)
            if res.status_code == 403:
                continue
            res.raise_for_status()
            return res.text
        except requests.exceptions.SSLError:
            if verify:
                verify = False
                continue
        except requests.RequestException:
            continue
    return None


def select_best_email(candidates, site_url, allow_external=False, allow_support=False):
    """Return the best e-mail candidate from ``candidates``.

    Each candidate is a mapping with ``email``, ``source_url`` and
    ``anchor_text`` keys.  ``site_url`` is used to determine whether the
    e-mail address belongs to the same site.  The function returns
    ``(best, notes, kept, blocked)`` where ``best`` is the chosen e-mail or
    ``None`` when no suitable address was found, ``notes`` is a list of
    diagnostic strings, ``kept`` is a list of kept e-mails and ``blocked`` is
    a list of ``(email, reason)`` tuples describing rejected candidates.
    """

    def _host_from_url(url: str) -> str:
        return urlparse(url).netloc.lower() if url else ""

    def _same_site(a: str, b: str) -> bool:
        return a == b or a.endswith("." + b)

    def _norm_local(local: str) -> str:
        local = local.lower().split("+", 1)[0]
        return local.replace(".", "")

    base_host = _host_from_url(site_url)

    BLOCK_LOCAL = (
        'jobs','job','career','careers','recruit','recruitment','hiring','hr','talent',
        'press','media','pr',
        'billing','invoice','accounting','finance',
        'legal','law','privacy','copyright','dmca','abuse','compliance','security',
        'admin','webmaster','postmaster','hostmaster',
        'noreply','donotreply'
    )
    SUPPORT_LOCAL = ('support','helpdesk','help')

    STRONG_PLUS = (
        'wholesale','purchasing','procurement','buyer','buying','sourcing',
        'supplier','supplies','supply','vendor','vendors',
        'trade','distributor','distribution','bulk'
    )
    MID_PLUS    = ('owner','manager','operations','beverage','fnb','foodandbeverage')
    SOFT_PLUS   = ('info','contact','hello','enquiries','inquiries','inquiry','team','partnership','partnerships')
    WEAK_PLUS   = ('sales','orders')

    CONSUMER_ORDER_PATH = (
        '/order','/order-online','/online-order','/orderonline',
        '/pickup','/takeout','/delivery','/menu','/menus','/catering','/gift-card','/giftcards'
    )
    CONSUMER_ANCHOR = (
        'order online','order now','takeout','pickup','delivery',
        'ubereats','doordash','grubhub','deliveroo','menu'
    )
    TRADE_HINTS = ('wholesale','trade','distributor','bulk','b2b','wholesale orders','trade orders')
    PURPOSE_PATH = (
        '/job','/jobs','/career','/careers','/recruit','/hiring',
        '/press','/media','/legal','/privacy','/terms','/dmca',
        '/billing','/invoice'
    )

    def score_one(e: dict, relax=False):
        email = (e.get('email') or '').strip()
        src = e.get('source_url') or ''
        anchor = (e.get('anchor_text') or '').lower()

        if not email or '@' not in email:
            return None

        if 'catering' in email.lower():
            return ('blocked', email, 'blocked:catering_address')

        local, domain = email.split('@', 1)
        nlocal = _norm_local(local)
        path = urlparse(src).path.lower() if src else ''

        if any(k in nlocal for k in BLOCK_LOCAL):
            return ('blocked', email, 'blocked:purpose_mismatch')
        if any(p in path for p in PURPOSE_PATH) or any(p in anchor for p in
            ('career','careers','recruit','hiring','press','media','legal','privacy','billing','invoice','dmca')):
            return ('blocked', email, 'blocked:purpose_section')

        if 'orders' in nlocal or nlocal == 'order':
            if any(p in path for p in CONSUMER_ORDER_PATH) or any(k in anchor for k in CONSUMER_ANCHOR):
                return ('blocked', email, 'blocked:consumer_order_inbox')
            if any(k in path for k in TRADE_HINTS) or any(k in anchor for k in TRADE_HINTS):
                extra_orders_bonus = 3
            else:
                extra_orders_bonus = 0
        else:
            extra_orders_bonus = 0

        s = 0
        if any(k in nlocal for k in STRONG_PLUS): s += 6
        if any(k in nlocal for k in MID_PLUS):    s += 4
        if any(k in nlocal for k in SOFT_PLUS):   s += 3
        if any(k in nlocal for k in WEAK_PLUS):   s += 1
        s += extra_orders_bonus

        same = _same_site(domain.lower(), _host_from_url(src) or base_host)
        if same: s += 2
        else:    s -= 1 if relax or allow_external else 2

        if any(k in nlocal for k in SUPPORT_LOCAL):
            if relax or allow_support:
                s -= 2
            else:
                return ('blocked', email, 'blocked:support_only')

        threshold = 1 if not relax else 0
        if s < threshold:
            return ('blocked', email, f'blocked:low_score({s})')

        tie = (
            0 if same else 1,
            - (6 if any(k in nlocal for k in STRONG_PLUS) else
               4 if any(k in nlocal for k in MID_PLUS) else
               3 if any(k in nlocal for k in SOFT_PLUS) else
               1 if any(k in nlocal for k in WEAK_PLUS) else 0) - extra_orders_bonus,
            len(local),
            email
        )
        return ('keep', email, s, tie)

    def run(relax=False):
        kept = []
        blocked = []
        for c in candidates:
            res = score_one(c, relax=relax)
            if not res:
                continue
            if res[0] == 'keep':
                kept.append(res[1:])
            else:
                blocked.append((res[1], res[2]))
        return kept, blocked

    kept, blocked = run(relax=False)
    notes = []
    if not kept:
        kept, blocked_relax = run(relax=True)
        blocked.extend(b for b in blocked_relax if b not in blocked)
        if kept:
            notes.append('relaxed')

    best = None
    if kept:
        kept.sort(key=lambda x: (-x[1], x[2]))
        best = kept[0][0]
    kept_emails = [k[0] for k in kept]
    return best, notes, kept_emails, blocked


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
    written_rows: list[int] = []
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
                email = crawl_site_for_email(
                    url, timeout=timeout, verify=verify_ssl
                ) or ""
                form = find_contact_form(
                    soup, url, timeout=timeout, verify=verify_ssl
                ) or ""
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
        written_rows.append(row_index)
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

    cleanup_enabled = os.getenv("CLEANUP_DUPLICATE_EMAIL_ROWS", "true").lower() == "true"
    email_col = os.getenv("EMAIL_COL_LETTER", "E")
    try:
        header_rows = int(os.getenv("HEADER_ROWS", "1"))
    except ValueError:
        header_rows = 1
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    if cleanup_enabled:
        if written_rows:
            try:
                deleted_written = cleanup_duplicates_written_only(
                    service=service,
                    spreadsheet_id=spreadsheet_id,
                    title=worksheet,
                    email_col_letter=email_col,
                    header_rows=header_rows,
                    written_rows=written_rows,
                    dry_run=dry_run,
                )
                if dry_run:
                    logging.info(
                        "[DRY_RUN] Would delete %s duplicate rows among this run.",
                        deleted_written,
                    )
                else:
                    logging.info(
                        "[CLEANUP] Deleted %s duplicate rows among this run.",
                        deleted_written,
                    )
            except Exception:  # pragma: no cover - cleanup errors shouldn't abort main flow
                logging.exception(
                    "[CLEANUP] Failed to clean up written-only duplicate rows"
                )
        else:
            logging.info("[CLEANUP] No rows were written; skip duplicate cleanup.")

        try:
            sheet_id = get_sheet_id(service, spreadsheet_id, worksheet)
            try:
                rows = find_rows_highlighted_as_duplicates(
                    service,
                    spreadsheet_id,
                    worksheet,
                    email_col,
                    header_rows,
                )
            except HttpError as exc:
                logging.warning(
                    "[CLEANUP] Color-based detection failed, falling back. reason=%s",
                    exc,
                )
                rows = []

            if not rows:
                rows = find_rows_by_programmatic_duplicates(
                    service,
                    spreadsheet_id,
                    worksheet,
                    email_col,
                    header_rows,
                )

            if rows:
                rows = sorted(set(rows), reverse=True)
                if dry_run:
                    logging.info("[DRY_RUN] Would delete %s rows: %s", len(rows), rows)
                else:
                    delete_rows(service, spreadsheet_id, sheet_id, rows)
                    logging.info("Deleted %s duplicate email rows.", len(rows))
            else:
                logging.info("No duplicate email rows to delete.")
        except Exception:  # pragma: no cover - cleanup errors shouldn't abort main flow
            logging.exception("Failed to clean up duplicate email rows")

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

