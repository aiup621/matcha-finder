import argparse
import csv
import logging
import os
import sys
from typing import List
from urllib.parse import urlparse

import requests

sys.path.append(os.path.dirname(__file__))
from verify_crawl import analyze_site  # noqa: E402

API_URL = "https://www.googleapis.com/customsearch/v1"
OFFICIAL_TLDS = (
    ".com",
    ".co",
    ".jp",
    ".net",
    ".org",
    ".us",
    ".uk",
    ".ca",
    ".au",
    ".de",
    ".fr",
    ".it",
    ".es",
    ".pt",
    ".kr",
    ".cn",
    ".tw",
    ".th",
)


def search(query: str, key: str, cx: str) -> List[str]:
    params = {"key": key, "cx": cx, "q": query}
    delay = 1
    for attempt in range(4):
        try:
            resp = requests.get(API_URL, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return [item.get("link") for item in data.get("items", [])]
            if resp.status_code in (429, 403) or resp.status_code >= 500 or "quota" in resp.text.lower():
                logging.warning("Search error %s: %s", resp.status_code, resp.text[:200])
                time.sleep(delay)
                delay *= 2
                continue
            logging.warning("Search unexpected status %s", resp.status_code)
            return []
        except requests.RequestException as exc:
            logging.warning("Search exception: %s", exc)
            time.sleep(delay)
            delay *= 2
    logging.info("Quota or persistent error, stopping search")
    return []


def pick_official(links: List[str]) -> str:
    for link in links:
        if link and urlparse(link).netloc.endswith(OFFICIAL_TLDS):
            return link
    return ""


def save_rows(path: str, rows: List[dict]):
    fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fallback search for missing sites")
    parser.add_argument("--country", required=True, help="ISO2 country code")
    parser.add_argument("--in", dest="infile", help="Input results CSV", default=None)
    parser.add_argument("--out", dest="outfile", help="Output results CSV", default=None)
    parser.add_argument("--budget", type=int, default=None, help="Search budget")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    key = os.getenv("GOOGLE_API_KEY", "")
    cx = os.getenv("GOOGLE_CX", "")
    if not key or not cx:
        logging.info("Google API key or CX missing, skipping search")
        return

    infile = args.infile or f"data/results_{args.country}.csv"
    outfile = args.outfile or infile
    budget = args.budget if args.budget is not None else int(os.getenv("SEARCH_BUDGET", "20"))

    with open(infile, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        if budget <= 0:
            logging.info("Search budget exhausted")
            break
        if row.get("site"):
            continue
        query = f"{row.get('name', '')} {row.get('city', '')} official site"
        links = search(query, key, cx)
        if not links:
            continue
        site = pick_official(links[:3])
        if not site:
            continue
        info = analyze_site(site)
        row.update({
            "site": info["site"],
            "has_matcha": str(info["has_matcha"]).lower(),
            "evidence_url": info["evidence_url"],
            "instagram": info["instagram"],
            "contact_email": info["contact_email"],
            "contact_form": info["contact_form"],
        })
        save_rows(outfile, rows)
        budget -= 1
    save_rows(outfile, rows)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
