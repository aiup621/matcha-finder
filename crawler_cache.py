from __future__ import annotations
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict

CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
CACHE_FILE = CACHE_DIR / "crawler_cache.json"
TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "30"))


def _now_date() -> str:
    return datetime.utcnow().date().isoformat()


def _purge(data: Dict[str, Dict[str, str]]) -> None:
    if TTL_DAYS <= 0:
        return
    cutoff = datetime.utcnow() - timedelta(days=TTL_DAYS)
    for key in ("seen_hosts", "seen_urls", "blocked_hosts_dynamic"):
        d = data.get(key, {})
        data[key] = {
            k: v
            for k, v in d.items()
            if datetime.fromisoformat(v) >= cutoff
        }


def load_cache(clear: bool | None = None) -> Dict[str, Dict[str, str]]:
    if clear is None:
        clear = os.getenv("CLEAR_CACHE") == "1"
    if clear or not CACHE_FILE.exists():
        data = {"seen_hosts": {}, "seen_urls": {}, "blocked_hosts_dynamic": {}}
        return data
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"seen_hosts": {}, "seen_urls": {}, "blocked_hosts_dynamic": {}}
    _purge(data)
    return data


def save_cache(cache: Dict[str, Dict[str, str]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _purge(cache)
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def has_seen(cache: Dict[str, Dict[str, str]], url: str) -> bool:
    host = urlparse(url).hostname or ""
    return url in cache.get("seen_urls", {}) or host in cache.get("seen_hosts", {})


def mark_seen(cache: Dict[str, Dict[str, str]], url: str) -> None:
    host = urlparse(url).hostname or ""
    today = _now_date()
    cache.setdefault("seen_urls", {})[url] = today
    cache.setdefault("seen_hosts", {})[host] = today


def add_blocked_host(cache: Dict[str, Dict[str, str]], host: str) -> None:
    cache.setdefault("blocked_hosts_dynamic", {})[host.lower()] = _now_date()


def is_blocked_host(cache: Dict[str, Dict[str, str]], host: str) -> bool:
    return host.lower() in cache.get("blocked_hosts_dynamic", {})


__all__ = [
    "load_cache",
    "save_cache",
    "has_seen",
    "mark_seen",
    "add_blocked_host",
    "is_blocked_host",
]
