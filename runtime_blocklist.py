from __future__ import annotations
from urllib.parse import urlparse
import re

BAD_REASONS = {"blocked_or_empty", "no_html", "status_401", "status_403", "js_required"}

class RuntimeBlockList:
    """Track domains that repeatedly fail or block requests."""
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.blocked: set[str] = set()

    def record(self, url: str, reason: str) -> None:
        if reason not in BAD_REASONS:
            return
        host = urlparse(url).hostname or ""
        c = self.counts.get(host, 0) + 1
        self.counts[host] = c
        if c >= 2:
            self.blocked.add(host)

    def is_blocked(self, url: str) -> bool:
        host = urlparse(url).hostname or ""
        return host in self.blocked

def requires_js(html: str) -> bool:
    """Heuristic to detect pages that require JS."""
    if not html:
        return False
    total = len(html.encode("utf-8"))
    if total >= 8 * 1024:
        return False
    script_bytes = sum(len(m.group(0)) for m in re.finditer(r"<script[^>]*>.*?</script>", html, re.I | re.S))
    return script_bytes / total > 0.35

__all__ = ["RuntimeBlockList", "requires_js", "BAD_REASONS"]
