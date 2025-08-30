import argparse
import csv
import logging
import sys
import time
from urllib.parse import urljoin, urlparse
import requests

from bs4 import BeautifulSoup

TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (matcha-finder; +https://example.com)"}
MATCHA_WORDS = [
    "matcha",
    "抹茶",
    "matcha latte",
    "iced matcha",
    "ceremonial matcha",
    "thé matcha",
    "latte matcha",
    "té matcha",
    "latte de matcha",
    "tè matcha",
    "tè al matcha",
    "chá matcha",
    "café matcha",
    "말차",
    "말차라떼",
    "抹茶拿铁",
    "抹茶牛奶",
    "ชาเขียวมัทฉะ",
    "มัทฉะ",
]
CONTACT_PATHS = [
    "contact",
    "contact-us",
    "kontakt",
    "contacto",
    "联系我们",
    "聯絡我們",
    "お問い合わせ",
]
CANDIDATE_PATHS = ["/", "/menu", "/drinks", "/tea"] + [f"/{p}" for p in CONTACT_PATHS]


def fetch(url: str):
    delay = 1
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            return resp
        except requests.RequestException as exc:
            logging.warning("Fetch error %s on %s", exc, url)
            time.sleep(delay)
            delay *= 2
    return None


def extract_instagram(soup: BeautifulSoup) -> str:
    link = soup.find("a", href=lambda h: h and "instagram.com" in h)
    if link and link.get("href"):
        return link["href"]
    link = soup.find("link", rel=lambda r: r and "me" in r, href=lambda h: h and "instagram.com" in h)
    if link and link.get("href"):
        return link["href"]
    return ""


def extract_email(soup: BeautifulSoup) -> str:
    link = soup.find("a", href=lambda h: h and h.startswith("mailto:"))
    if link and link.get("href"):
        return link["href"].split(":", 1)[1]
    return ""


def analyze_site(site: str) -> dict:
    if not site:
        return {"site": "", "has_matcha": False, "evidence_url": "", "instagram": "", "contact_email": "", "contact_form": ""}
    if not site.startswith("http"):
        site = "http://" + site
    parsed = urlparse(site)
    base = f"{parsed.scheme}://{parsed.netloc}"
    result = {"site": base, "has_matcha": False, "evidence_url": "", "instagram": "", "contact_email": "", "contact_form": ""}
    for path in CANDIDATE_PATHS:
        url = urljoin(base, path)
        resp = fetch(url)
        if not resp or resp.status_code >= 400:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ").lower()
        if not result["instagram"]:
            result["instagram"] = extract_instagram(soup)
        if not result["contact_email"]:
            result["contact_email"] = extract_email(soup)
        if not result["contact_form"] and any(cp in path for cp in CONTACT_PATHS):
            result["contact_form"] = url
        if not result["has_matcha"]:
            for kw in MATCHA_WORDS:
                if kw.lower() in text:
                    result["has_matcha"] = True
                    result["evidence_url"] = url
                    break
        if result["has_matcha"] and result["instagram"] and result["contact_email"] and result["contact_form"]:
            break
    time.sleep(0.3)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify cafe sites for matcha and contacts")
    parser.add_argument("--in", dest="infile", required=True, help="Input CSV path")
    parser.add_argument("--out", dest="outfile", required=True, help="Output CSV path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    with open(args.infile, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    results = []
    for row in rows:
        site = row.get("website") or row.get("contact:website") or row.get("site")
        info = analyze_site(site)
        results.append({
            "source_id": row.get("id", ""),
            "name": row.get("name", ""),
            "city": row.get("addr:city", ""),
            "country": row.get("addr:country", ""),
            "site": info["site"],
            "has_matcha": str(info["has_matcha"]).lower(),
            "evidence_url": info["evidence_url"],
            "instagram": info["instagram"],
            "contact_email": info["contact_email"],
            "contact_form": info["contact_form"],
        })

    with open(args.outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_id",
            "name",
            "city",
            "country",
            "site",
            "has_matcha",
            "evidence_url",
            "instagram",
            "contact_email",
            "contact_form",
        ])
        writer.writeheader()
        writer.writerows(results)
    logging.info("Wrote %s", args.outfile)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
