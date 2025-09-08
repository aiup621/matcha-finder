import logging
from collections import deque
from typing import Optional, Dict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from email_extractors import extract_emails, FREEMAILS

SLUGS = [
    "/contact",
    "/contact-us",
    "/about",
    "/info",
    "/visit",
    "/find-us",
    "/connect",
]

EMAIL_BLOCKLIST = ("catering", "career")


def collect_emails(base_url: str, timeout: int = 5, verify: bool = True) -> Optional[Dict[str, str]]:
    """Return the best email found on ``base_url`` or related pages."""

    parsed = urlparse(base_url)
    domain = parsed.netloc
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    queue = deque([(base_url, 0)])
    visited = set()
    # enqueue slug pages
    origin = f"{parsed.scheme}://{parsed.netloc}"
    added = 0
    for slug in SLUGS:
        if added >= 3:
            break
        link = urljoin(origin + "/", slug.lstrip("/"))
        if link not in visited:
            queue.append((link, 1))
            added += 1

    candidates = []

    while queue:
        url, depth = queue.popleft()
        if url in visited or depth > 1:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, timeout=timeout, verify=verify, headers=headers)
            status = resp.status_code
            final_url = resp.url
            content = resp.text
            resp.raise_for_status()
        except requests.RequestException as exc:
            logging.info("FETCH %s error=%s", url, exc)
            continue

        soup = BeautifulSoup(content, "html.parser")
        found = extract_emails(soup)
        surfaces = {f["surface"] for f in found}
        logging.info(
            "FETCH %s status=%s final=%s bytes=%d matched=%s",
            url,
            status,
            final_url,
            len(content.encode("utf-8")),
            ",".join(sorted(surfaces)) if surfaces else "-",
        )

        for item in found:
            email = item["email"]
            if any(b in email.lower() for b in EMAIL_BLOCKLIST):
                continue
            page_path = urlparse(final_url).path or "/"
            candidates.append({
                "email": email,
                "surface": item["surface"],
                "page": page_path,
            })

        if not found and depth < 1:
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"])
                if urlparse(link).netloc == domain and link not in visited:
                    queue.append((link, depth + 1))

    if not candidates:
        return None

    base_domain = domain.lower()

    def score(email: str) -> float:
        dom = email.split("@", 1)[1].lower()
        if dom.endswith(base_domain):
            return 0.9
        if dom in FREEMAILS:
            return 0.5
        return 0.7

    for c in candidates:
        c["confidence"] = score(c["email"])

    best = max(candidates, key=lambda c: c["confidence"])
    return best
