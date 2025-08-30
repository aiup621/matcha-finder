import re

BASE_TEMPLATES = [
    "matcha cafe {city} website",
    "{city} matcha cafe official site",
    "best matcha {city} cafe website",
    "third wave coffee {city} matcha website",
    "artisan cafe {city} website matcha",
]


def _sanitize_query(q: str) -> str:
    q = re.sub(r"\bsite:\.com\b", "", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q

__all__ = ["BASE_TEMPLATES", "_sanitize_query"]
