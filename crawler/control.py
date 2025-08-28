from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
from typing import Deque, Tuple


@dataclass
class RunState:
    """State tracker for a crawl run.

    It keeps statistics required to decide rotation, phase escalation
    and termination. The object itself is intentionally free of side
    effects so that it can easily be unit-tested.
    """

    target: int
    max_queries: int
    max_rotations: int
    skip_rotate_threshold: int
    cache_burst_threshold: float = 0.5
    added: int = 0
    queries: int = 0
    rotations: int = 0
    consecutive_skips: int = 0
    phase: int = 1
    _last_added: int = 0
    recent_cache: Deque[int] = field(default_factory=lambda: deque(maxlen=20))
    cache_burst: bool = False

    def record_skip(self, reason: str) -> None:
        """Record a skip and update cache statistics."""
        self.consecutive_skips += 1
        if reason == "cache-hit":
            self.recent_cache.append(1)
        else:
            self.recent_cache.append(0)
        if self.recent_cache:
            ratio = sum(self.recent_cache) / len(self.recent_cache)
            self.cache_burst = (
                ratio >= self.cache_burst_threshold and self.added < self.target
            )
        else:
            self.cache_burst = False

    def record_add(self) -> None:
        """Record a successful add and reset counters."""
        self.added += 1
        self.consecutive_skips = 0
        self.recent_cache.clear()
        self.cache_burst = False
        self._last_added = self.added
        self.phase = 1

    def should_rotate(self) -> bool:
        """Return ``True`` when a rotation should occur."""
        if self.consecutive_skips >= self.skip_rotate_threshold:
            self.consecutive_skips = 0
            if self.rotations < self.max_rotations:
                self.rotations += 1
                return True
        return False

    def escalate_phase(self) -> int:
        """Advance to the next escalation phase."""
        if self.added > self._last_added:
            self._last_added = self.added
            self.phase = 1
        else:
            self.phase = min(self.phase + 1, 6)
        return self.phase

    def should_stop(
        self,
        *,
        no_candidates: bool = False,
        fatal_error: str | None = None,
    ) -> Tuple[bool, str]:
        """Determine whether the crawl should terminate."""
        if self.added >= self.target:
            return True, "target_met"
        if self.queries >= self.max_queries:
            return True, "max_queries"
        if fatal_error:
            return True, fatal_error
        if no_candidates:
            return True, "no_candidates"
        return False, ""


def format_stop(reason: str, state: RunState) -> str:
    """Create a unified stop log message."""
    return (
        f"[STOP] reason={reason} added={state.added}/{state.target} "
        f"rotations={state.rotations}/{state.max_rotations} "
        f"queries={state.queries}/{state.max_queries}"
    )


__all__ = ["RunState", "format_stop"]
