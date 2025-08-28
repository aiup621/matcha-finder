from __future__ import annotations
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


def load_domain_blocklist(path: str | Path) -> list[str]:
    """Load a domain block list file.

    Blank lines and comments starting with ``#`` are ignored.  Returned values
    are normalised to lower case.
    """
    p = Path(path)
    if not p.exists():
        return []
    out: list[str] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line.lower())
    return out


def _host_from_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.lower()


def is_blocked_domain(url: str, patterns: Iterable[str]) -> bool:
    """Return ``True`` if ``url`` matches one of the blocked domain patterns."""
    host = _host_from_url(url)
    for pat in patterns:
        if pat.startswith("*."):
            suf = pat[2:]
            if host == suf or host.endswith("." + suf):
                return True
        else:
            if host == pat or host.endswith("." + pat):
                return True
    return False


__all__ = ["load_domain_blocklist", "is_blocked_domain"]
