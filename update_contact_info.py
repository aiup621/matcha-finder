import argparse
import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REQUEST_TIMEOUT = 5

DEFAULT_SHEET_PATH = (
    "https://docs.google.com/spreadsheets/d/1HU-GqN7sBcORIZrYEw4FkyfNmgDtXsO7CtDLVHEsldA/"
    "edit?gid=159511499#gid=159511499"
)


def find_instagram(soup, base_url):
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "instagram.com" in href:
            return href if href.startswith("http") else urljoin(base_url, href)
    return None


def find_email(soup):
    """Extract an email address from the page soup.

    The previous implementation only matched ``mailto:`` links written in
    lowercase.  Some sites, however, use capitalised schemes such as
    ``MAILTO:`` which caused the function to miss valid e-mail addresses.

    This version performs a case-insensitive search for ``mailto`` links and
    strips the scheme in a case-insensitive manner as well.  If no explicit
    ``mailto`` link is present, it falls back to searching the page text with
    a regular expression.
    """
    mailto = soup.find("a", href=lambda h: h and h.lower().startswith("mailto:"))
    if mailto and mailto.get("href"):
        href = mailto["href"]
        # Remove the leading scheme (case-insensitively) and any query string
        return re.sub(r"^mailto:", "", href, flags=re.I).split("?")[0]
    match = EMAIL_RE.search(soup.get_text())
    if match:
        return match.group(0)
    return None


def find_contact_form(soup, base_url):
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").lower()
        href = a["href"]
        keywords = ["contact", "お問い合わせ", "お問合せ", "inquiry"]
        if any(k in text for k in keywords) or any(k in href.lower() for k in keywords + ["form"]):
            return href if href.startswith("http") else urljoin(base_url, href)
    return None


def process_sheet(path, start_row=None, end_row=None, worksheet="抹茶営業リスト（カフェ）", debug=False):
    import io
    import urllib.parse
    import openpyxl

    if debug:
        logging.basicConfig(level=logging.INFO)

    # URLが来た場合はダウンロードして BytesIO から読み込む。
    # Google Sheets の場合は export エンドポイントに書き換え。
    save_path = path
    if isinstance(path, str) and path.startswith("http"):
        download_url = path
        if "docs.google.com/spreadsheets" in path and "/export" not in path:
            parsed = urllib.parse.urlparse(path)
            match = re.search(r"/d/([^/]+)", parsed.path)
            if match:
                file_id = match.group(1)
                qs = urllib.parse.parse_qs(parsed.query)
                gid = qs.get("gid", ["0"])[0]
                download_url = (
                    f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx&gid={gid}"
                )
        resp = requests.get(download_url)
        resp.raise_for_status()
        path = io.BytesIO(resp.content)
        save_path = "downloaded.xlsx"

    wb = openpyxl.load_workbook(path)
    ws = wb[worksheet]

    # Determine start and end rows.  If both are unspecified and the sheet
    # contains ``Action`` metadata in the first row, honour those values.
    # Otherwise, default to starting from row 2 and processing until the last
    # row in the sheet.  This ensures that explicitly providing ``start_row``
    # via the command line causes the script to keep scanning downward until
    # column A becomes blank, regardless of any value in ``C1``.
    if start_row is None and end_row is None and ws["A1"].value == "Action":
        try:
            start_row = int(ws["B1"].value)
        except (TypeError, ValueError):
            start_row = 2
        try:
            end_row = int(ws["C1"].value)
        except (TypeError, ValueError):
            end_row = ws.max_row
    else:
        if start_row is None:
            start_row = 2
        if end_row is None:
            end_row = ws.max_row

    end_row = min(end_row, ws.max_row)

    for row in range(start_row, end_row + 1):
        # A列が空なら以降は処理しない
        if not ws.cell(row=row, column=1).value:
            break
        url = ws.cell(row=row, column=3).value
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not url.lower().startswith(("http://", "https://")):
            logging.warning("Skipping invalid URL at row %s: %r", row, url)
            continue
        logging.info("Processing row %s: %s", row, url)
        try:
            res = requests.get(url, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.SSLError:
            try:
                res = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False)
            except requests.RequestException as e:
                logging.warning(
                    "Request failed for row %s (%s): %s", row, url, e
                )
                ws.cell(row=row, column=7).value = "エラー"
                continue
        except requests.RequestException as e:
            logging.warning("Request failed for row %s (%s): %s", row, url, e)
            ws.cell(row=row, column=7).value = "エラー"
            continue
        soup = BeautifulSoup(res.text, "html.parser")
        insta = find_instagram(soup, url)
        email = find_email(soup)
        form = find_contact_form(soup, url)
        if insta:
            ws.cell(row=row, column=4).value = insta
        if email:
            ws.cell(row=row, column=5).value = email
        if form:
            ws.cell(row=row, column=6).value = form
        if not any([insta, email, form]):
            ws.cell(row=row, column=7).value = "なし"
        logging.info(
            "Row %s result - Insta: %s, Email: %s, Form: %s",
            row, bool(insta), bool(email), bool(form)
        )
    wb.save(save_path)


def main():
    parser = argparse.ArgumentParser(description="Update contact info from homepage URLs.")
    parser.add_argument(
        "sheet",
        nargs="?",
        default=DEFAULT_SHEET_PATH,
        help="Path to Excel file to update",
    )
    parser.add_argument("--start-row", type=int, default=None, help="Row number to start processing")
    parser.add_argument("--end-row", type=int, default=None, help="Row number to stop processing (inclusive)")
    parser.add_argument("--worksheet", default="抹茶営業リスト（カフェ）", help="Worksheet name to process")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    process_sheet(args.sheet, args.start_row, args.end_row, args.worksheet, args.debug)


if __name__ == "__main__":
    main()
