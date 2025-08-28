from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict
try:  # PyYAML is optional
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback if PyYAML is absent
    yaml = None

DEFAULT_SETTINGS: Dict[str, Any] = {
    "SKIP_THRESHOLD": 15,
    "INTENT_TERMS": [
        "latte",
        "menu",
        "hours",
        "about",
        "story",
        "店舗情報",
        "メニュー",
    ],
    "NEGATIVE_SITES": [
        "facebook.com",
        "square.site",
        "mapquest.com",
        "toasttab.com",
        "westfield.com",
        "rockefellercenter.com",
    ],
}

_SETTINGS_CACHE: Dict[str, Any] | None = None


def load_settings() -> Dict[str, Any]:
    """Load crawler settings from ``config/settings.yaml``.

    The file is optional; if it is missing, a set of defaults is returned.  The
    result is cached to avoid repeated disk access.
    """
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE

    path = Path(os.getenv("SETTINGS_PATH", "config/settings.yaml"))
    data: Dict[str, Any] = {}
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8")
            if yaml is not None:
                loaded = yaml.safe_load(text) or {}
            else:
                loaded = _parse_simple_yaml(text)
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            # Ignore parse errors and fall back to defaults
            pass
    for k, v in DEFAULT_SETTINGS.items():
        data.setdefault(k, v)
    _SETTINGS_CACHE = data
    return data


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Very small YAML subset parser used when PyYAML is unavailable."""
    data: Dict[str, Any] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not line.startswith("-"):
            current = line[:-1].strip()
            data[current] = []
            continue
        if ":" in line and not line.startswith("-"):
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if val.isdigit():
                data[key] = int(val)
            else:
                data[key] = val
            current = None
            continue
        if line.startswith("-") and current:
            item = line[1:].strip().strip("\"'")
            data.setdefault(current, []).append(item)
    return data
__all__ = ["load_settings"]
