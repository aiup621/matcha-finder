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
    "matcha soft serve",
    "house-made matcha",
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
    """Build English-only queries with rotation support.

    The builder is intentionally minimal; higher level control such as
    escalation phases is handled by :class:`RunState` in
    ``crawler.control``.  ``QueryBuilder`` simply exposes hooks to
    modify the base terms used for query construction.
    """

    def __init__(
        self,
        blocklist: Iterable[str] | None = None,
        *,
        city_seeds: Iterable[str] | None = None,
        rotate_threshold: int | None = None,
        max_rotations: int | None = None,
        enforce_english: bool | None = None,
    ) -> None:
        env_force = bool(int(os.getenv("FORCE_ENGLISH_QUERIES", "0")))
        self.enforce_english = env_force if enforce_english is None else enforce_english
        block_env = os.getenv("EXCLUDE_DOMAINS", "")
        block_extra = os.getenv("EXCLUDE_DOMAINS_EXTRA", "")
        env_blocks = [
            s.strip().lower()
            for s in f"{block_env},{block_extra}".split(",")
            if s.strip()
        ]
        combined = list(blocklist or []) + env_blocks
        self.blocklist = [self._to_ascii(s.strip().lower()) for s in combined if s.strip()]
        seed_env = os.getenv("CITY_SEEDS")
        if seed_env:
            seeds = [self._to_ascii(s.strip()) for s in seed_env.split(",") if s.strip()]
        else:
            seeds = list(city_seeds) if city_seeds else DEFAULT_SEEDS
            seeds = [self._to_ascii(s) for s in seeds]
        self.cities: List[str] = seeds
        self.city_idx = 0
        self.base_terms: List[str] = [self._to_ascii(t) for t in BASE_TERMS_CORE]
        self.context_boosters: List[str] = [self._to_ascii(t) for t in CONTEXT_BOOSTERS]
        self.rotate_threshold = int(
            os.getenv("SKIP_ROTATE_THRESHOLD", rotate_threshold or 8)
        )
        self.max_rotations = int(os.getenv("MAX_ROTATIONS_PER_RUN", max_rotations or 4))
        self.consec_skips = 0
        self.rotations = 0
        self.rotation_log: List[Tuple[str, str, str]] = []
        self.include_synonyms = False
        self.force_tight_context = False

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

    def _to_ascii(self, text: str) -> str:
        return ascii_only(text) if self.enforce_english else text

    def set_phase(self, phase: int) -> None:
        """Adjust internal flags according to escalation phase."""
        self.base_terms = [self._to_ascii(t) for t in BASE_TERMS_CORE]
        if phase >= 2:
            self.base_terms.extend(self._to_ascii(t) for t in BASE_TERMS_SYNONYMS)
        self.include_synonyms = phase >= 2
        self.force_tight_context = phase >= 3

    def build_queries(self) -> List[str]:
        city = self._to_ascii(self.current_city())
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
                q = self._to_ascii(q)[:256]
                assert len(q) <= 256
                queries.append(q)
            if len(queries) >= 12:
                break
        # ensure uniqueness
        uniq: List[str] = []
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
        action = "swap_city"
        from_city = self.current_city()
        if self.cities:
            self.city_idx = (self.city_idx + 1) % len(self.cities)
        to_city = self.current_city()
        self.rotation_log.append((action, from_city, to_city))
        self.rotations += 1
        return True

    def rotation_summary(self) -> List[Tuple[str, str, str]]:
        return self.rotation_log

__all__ = ["QueryBuilder", "ascii_only"]
