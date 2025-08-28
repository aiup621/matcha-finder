import json
import os
from typing import List

class QueryBuilder:
    def __init__(self, intent_file: str = os.getenv("INTENT_FILE", "config/query_intent.json"), rotate_threshold: int = None):
        try:
            with open(intent_file, "r", encoding="utf-8") as f:
                self.intent = json.load(f)
        except FileNotFoundError:
            self.intent = {}
        self.must_terms: List[str] = self.intent.get("must_terms", [])
        self.context_terms: List[str] = self.intent.get("context_terms", [])
        self.exclude_sites: List[str] = self.intent.get("exclude_sites", [])
        self.cities: List[str] = self.intent.get("seed_cities", [])
        self.city_idx = 0
        self.ctx_idx = 0
        if rotate_threshold is not None:
            self.rotate_threshold = int(rotate_threshold)
        else:
            self.rotate_threshold = int(os.getenv("SKIP_ROTATE_THRESHOLD", 25))
        self.consec_skips = 0

    def _join_or(self, terms: List[str]) -> str:
        return "(" + " OR ".join(terms) + ")" if terms else ""

    def current_city(self) -> str:
        return self.cities[self.city_idx % len(self.cities)] if self.cities else ""

    def build(self) -> str:
        must = self._join_or(self.must_terms)
        ctx_terms = self._join_or(self.context_terms)
        parts = [must]
        if ctx_terms:
            parts.extend(["AND", ctx_terms])
        city = self.current_city()
        if city:
            parts.append(f'"{city}"')
        excl = [f"-site:{s}" for s in self.exclude_sites]
        query = " ".join(parts + excl)
        # Trim only when exclude list is large to keep common sites intact
        if len(self.exclude_sites) > 10 and len(query) > 250:
            keep = []
            for e in excl:
                tmp = " ".join(parts + keep + [e])
                if len(tmp) > 250:
                    break
                keep.append(e)
            query = " ".join(parts + keep)
        return query.strip()

    def record_skip(self):
        self.consec_skips += 1
        if self.consec_skips >= self.rotate_threshold:
            self._rotate()
            self.consec_skips = 0

    def record_hit(self):
        self.consec_skips = 0

    def _rotate(self):
        # simple rotation: swap city and context term order
        if self.cities:
            old_city = self.current_city()
            self.city_idx = (self.city_idx + 1) % len(self.cities)
            new_city = self.current_city()
            print(f"[ROTATE] consecutive_skips={self.rotate_threshold} -> action=swap_city from={old_city} to={new_city}")
        if self.context_terms:
            self.context_terms = self.context_terms[1:] + self.context_terms[:1]

__all__ = ["QueryBuilder"]
