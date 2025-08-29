from __future__ import annotations
import os, uuid, hashlib
from dataclasses import dataclass
from datetime import date

@dataclass
class EnvConfig:
    CACHE_VERSION: str = os.getenv("CACHE_VERSION", "v1")
    EXCLUDE_DOMAINS_EXTRA: str = os.getenv("EXCLUDE_DOMAINS_EXTRA", "")
    FORCE_ENGLISH_QUERIES: int = int(os.getenv("FORCE_ENGLISH_QUERIES", "0"))
    SKIP_ROTATE_THRESHOLD: int = max(8, int(os.getenv("SKIP_ROTATE_THRESHOLD", "8")))
    CACHE_DATE: str = date.today().strftime("%Y%m%d")

class Cache:
    """Lightweight cache namespace helper."""
    def __init__(self, env: EnvConfig | None = None, *, phase: int = 1, cache_bust: bool = False):
        self.env = env or EnvConfig()
        self.phase = phase
        self._suffix = uuid.uuid4().hex[:8] if cache_bust else ""
        self.visited_urls: set[str] = set()

    def namespace(self) -> str:
        ns = f"{self.env.CACHE_DATE}-{self.env.CACHE_VERSION}"
        if self.phase >= 3:
            ns = f"{ns}:p{self.phase}"
        if self._suffix:
            ns = f"{ns}:{self._suffix}"
        return ns

    def key(self, url: str) -> str:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return f"{self.namespace()}:{h}"

    def seen(self, url: str) -> bool:
        k = self.key(url)
        if k in self.visited_urls:
            return True
        self.visited_urls.add(k)
        return False

__all__ = ["EnvConfig", "Cache"]
