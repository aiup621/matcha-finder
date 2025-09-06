import argparse
import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

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

def process_sheet(path, start_row=None, debug=False):
    import openpyxl

    if debug:
        logging.basicConfig(level=logging.INFO)

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    if start_row is None:
        if ws["A1"].value == "Action":
            try:
                start_row = int(ws["B1"].value)
            except (TypeError, ValueError):
                start_row = 2
        else:
            start_row = 2
    for row in range(start_row, ws.max_row + 1):
        url = ws.cell(row=row, column=3).value
        if not url:
            continue
        logging.info("Processing row %s: %s", row, url)
        try:
            res = requests.get(url, timeout=10)
        except requests.RequestException as e:
            logging.warning("Request failed for %s: %s", url, e)
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
        # Persist the next row to process so repeated runs can resume
        if ws["A1"].value == "Action":
            ws["B1"].value = row + 1
        logging.info(
            "Row %s result - Insta: %s, Email: %s, Form: %s",
            row,
            bool(insta),
            bool(email),
            bool(form),
        )
    wb.save(path)

def main():
    parser = argparse.ArgumentParser(description="Update contact info from homepage URLs.")
    parser.add_argument("sheet", help="Path to Excel file to update")
    parser.add_argument("--start-row", type=int, default=None, help="Row number to start processing")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    process_sheet(args.sheet, args.start_row, args.debug)

if __name__ == "__main__":
    main()
