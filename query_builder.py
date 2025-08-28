from __future__ import annotations
from typing import Dict, Iterable
from config_loader import load_settings


def _dedup(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def build_query(seed: Dict[str, str]) -> str:
    """Build a Google CSE query using ``seed`` information.

    Parameters
    ----------
    seed:
        Dictionary containing optional keys such as ``city``, ``state`` and
        ``keywords``.  All non-empty values are concatenated to the base query
        that boosts intent terms and excludes unwanted sites.
    """
    settings = load_settings()
    neg_sites = _dedup(settings.get("NEGATIVE_SITES", []))
    intent_terms = _dedup(settings.get("INTENT_TERMS", []))

    base_parts = ['("matcha" OR "\u629c\u8336")']
    if intent_terms:
        intent = "(" + " OR ".join(intent_terms) + ")"
        base_parts.append("AND")
        base_parts.append(intent)

    seed_terms = _dedup(
        [seed.get("city", ""), seed.get("state", ""), seed.get("keywords", ""), seed.get("zip", "")]
    )
    if seed_terms:
        base_parts.append(" ".join(seed_terms))
    query = " ".join(base_parts)

    if neg_sites:
        neg = " ".join(f"-site:{s}" for s in neg_sites)
        query = f"{query} {neg}".strip()

    # Custom search has a limit on query length (2048 for URL, but keep modest)
    if len(query) > 250:
        query = query[:250]
    return query


__all__ = ["build_query"]
