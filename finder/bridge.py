from bs4 import BeautifulSoup
from urllib.parse import urlsplit, parse_qs

BRIDGE_ALLOW = (
    "yelp.com",
    "maps.google.",
    "instagram.com",
    "opentable.com",
    "toasttab.com",
    "doordash.com",
    "ubereats.com",
)


def can_bridge(url: str) -> bool:
    return any(d in url for d in BRIDGE_ALLOW)


def _from_yelp(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        t = (a.get_text() or "").strip().lower()
        if t in {"website", "official website", "visit website"} or "biz_redir?url=" in a["href"]:
            href = a["href"]
            if "biz_redir?url=" in href:
                q = parse_qs(urlsplit(href).query).get("url", [href])[0]
                return q
            return href
    return None


def extract_official(url: str, html: str) -> str | None:
    if "yelp.com" in url:
        return _from_yelp(html)
    # future: maps/instagram/others
    return None

__all__ = ["can_bridge", "extract_official", "BRIDGE_ALLOW"]
