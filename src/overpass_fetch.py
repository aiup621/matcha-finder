import argparse
import csv
import logging
import sys
import time
from typing import Dict

import requests

API_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "matcha-finder/0.1 (+https://example.com)"}


def fetch(country: str) -> Dict:
    query = f"""
    [out:json][timeout:60];
    area["ISO3166-1"="{country}"][admin_level=2];
    (
      node["amenity"="cafe"](area);
      node["shop"="tea"](area);
      way["amenity"="cafe"](area);
      way["shop"="tea"](area);
    );
    out center tags;
    """
    delay = 1
    for attempt in range(3):
        try:
            logging.info("Querying Overpass for %s (attempt %s)", country, attempt + 1)
            resp = requests.post(API_URL, data={"data": query}, headers=HEADERS, timeout=120)
            if resp.status_code == 200:
                time.sleep(1)
                return resp.json()
            logging.warning("Overpass status %s", resp.status_code)
        except requests.RequestException as exc:
            logging.warning("Overpass error: %s", exc)
        time.sleep(delay)
        delay *= 2
    return {"elements": []}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch cafe websites from Overpass")
    parser.add_argument("--country", required=True, help="ISO2 country code")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    data = fetch(args.country)
    elements = data.get("elements", [])
    logging.info("Fetched %d elements", len(elements))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id",
            "name",
            "addr:city",
            "addr:country",
            "website",
            "contact:website",
            "contact:instagram",
            "contact:email",
        ])
        for el in elements:
            tags = el.get("tags", {})
            row = [
                el.get("id", ""),
                tags.get("name", ""),
                tags.get("addr:city", ""),
                tags.get("addr:country", ""),
                tags.get("website", ""),
                tags.get("contact:website", ""),
                tags.get("contact:instagram", ""),
                tags.get("contact:email", ""),
            ]
            writer.writerow(row)
    logging.info("Wrote %s", args.out)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
