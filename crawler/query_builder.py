from __future__ import annotations
import os
from typing import Iterable, List, Tuple

BASE_TERMS_CORE: List[str] = [
    "matcha latte",
    "matcha cafe",
    "matcha menu",
]
BASE_TERMS_SYNONYMS: List[str] = [
    "green tea latte",
    "ceremonial matcha",
]
CONTEXT_BOOSTERS: List[str] = [
    "menu",
    "hours",
    "about",
    "contact",
    "drink",
    "beverage",
]
BUSINESS_SITES = "(site:.com OR site:.net OR site:.org OR site:.coffee OR site:.cafe)"
DEFAULT_SEEDS: List[str] = [
    "San Antonio, TX",
    "Seattle, WA",
    "Austin, TX",
    "Houston, TX",
    "Boston, MA",
    "Denver, CO",
    "Portland, OR",
    "Tampa, FL",
]

def ascii_only(text: str) -> str:
    return text.encode("ascii", "ignore").decode()

class QueryBuilder:
    """Build English-only queries with rotation support."""

    def __init__(
        self,
        blocklist: Iterable[str] | None = None,
        *,
        city_seeds: Iterable[str] | None = None,
        rotate_threshold: int | None = None,
        max_rotations: int | None = None,
    ) -> None:
        self.blocklist = [ascii_only(s.strip().lower()) for s in (blocklist or []) if s.strip()]
        seed_env = os.getenv("CITY_SEEDS")
        if seed_env:
            seeds = [ascii_only(s.strip()) for s in seed_env.split(",") if s.strip()]
        else:
            seeds = list(city_seeds) if city_seeds else DEFAULT_SEEDS
            seeds = [ascii_only(s) for s in seeds]
        self.cities: List[str] = seeds
        self.city_idx = 0
        self.base_terms: List[str] = [ascii_only(t) for t in BASE_TERMS_CORE]
        self.synonyms_added = False
        self.context_boosters: List[str] = [ascii_only(t) for t in CONTEXT_BOOSTERS]
        self.force_tight_context = False
        self.rotate_threshold = int(os.getenv("SKIP_ROTATE_THRESHOLD", rotate_threshold or 20))
        self.max_rotations = int(os.getenv("MAX_ROTATIONS_PER_RUN", max_rotations or 4))
        self.consec_skips = 0
        self.rotations = 0
        self.rotation_log: List[Tuple[str, str, str]] = []

    # -------- query construction ---------
    def _neg_sites(self, current: str) -> str:
        parts: List[str] = []
        for site in self.blocklist:
            token = f"-site:{site}"
            if len(f"{current} {' '.join(parts+[token])}") > 250:
                break
            parts.append(token)
        return " ".join(parts)

    def _apply_business_sites(self, q: str) -> str:
        if len(f"{q} {BUSINESS_SITES}") <= 256:
            return f"{q} {BUSINESS_SITES}"
        return q

    def build_queries(self) -> List[str]:
        city = ascii_only(self.current_city())
        patterns = [
            lambda b: f'"{b}" AND (menu OR hours OR contact)',
            lambda b: f'"{b}" AND menu',
            lambda b: f'"{b}" AND (drink OR beverage)',
        ]
        if self.force_tight_context:
            patterns = [
                lambda b: f'"{b}" AND (menu OR hours OR contact)',
                lambda b: f'"{b}" AND menu',
            ]
        queries: List[str] = []
        for b in self.base_terms:
            for pat in patterns:
                if len(queries) >= 12:
                    break
                core = f"{pat(b)} AND {city}"
                neg = self._neg_sites(core)
                q = core if not neg else f"{core} {neg}"
                q = self._apply_business_sites(q)
                q = ascii_only(q)[:256]
                assert len(q) <= 256
                queries.append(q)
            if len(queries) >= 12:
                break
        # ensure uniqueness
        uniq = []
        seen = set()
        for q in queries:
            if q not in seen:
                seen.add(q)
                uniq.append(q)
        return uniq

    # -------- rotation handling --------
    def current_city(self) -> str:
        if not self.cities:
            return ""
        return self.cities[self.city_idx % len(self.cities)]

    def record_skip(self) -> bool:
        self.consec_skips += 1
        if self.consec_skips >= self.rotate_threshold:
            self.consec_skips = 0
            return self._rotate()
        return False

    def record_hit(self) -> None:
        self.consec_skips = 0

    def _rotate(self) -> bool:
        if self.rotations >= self.max_rotations:
            return False
        order = ["swap_city", "expand_synonyms", "tighten_context", "swap_city"]
        action = order[self.rotations % len(order)]
        from_city = self.current_city()
        if action == "swap_city" and self.cities:
            self.city_idx = (self.city_idx + 1) % len(self.cities)
            to_city = self.current_city()
            self.rotation_log.append((action, from_city, to_city))
        elif action == "expand_synonyms":
            if not self.synonyms_added:
                self.base_terms.extend(ascii_only(t) for t in BASE_TERMS_SYNONYMS)
                self.synonyms_added = True
            self.rotation_log.append((action, from_city, from_city))
        elif action == "tighten_context":
            self.force_tight_context = True
            self.rotation_log.append((action, from_city, from_city))
        self.rotations += 1
        return True

    def rotation_summary(self) -> List[Tuple[str, str, str]]:
        return self.rotation_log

__all__ = ["QueryBuilder", "ascii_only"]
