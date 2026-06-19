"""DailyPicker — the pure, deterministic chooser.

Given a date and finite candidate pools, it returns the same selection every
time, excluding anything already seen. No network, no model, no clock — which
is exactly what makes it the prime unit-test target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .seeding import seed_for, shuffled


@dataclass
class Selection:
    artwork_id: str
    poem_id: str


class DailyPicker:
    def pick(
        self,
        date: str,
        artwork_pool: Iterable[str],
        poem_pool: Iterable[str],
        seen: Iterable[str] = (),
    ) -> Selection:
        seen_set = {str(s) for s in seen}
        return Selection(
            artwork_id=self._choose(f"{date}:artwork", artwork_pool, seen_set),
            poem_id=self._choose(f"{date}:poem", poem_pool, seen_set),
        )

    def _choose(self, key: str, pool: Iterable[str], seen: set[str]) -> str:
        pool = [str(x) for x in pool]
        available = sorted(x for x in pool if x not in seen)
        if not available:
            # Everything's been seen — rather than fail the ritual, allow repeats.
            available = sorted(pool)
        if not available:
            raise ValueError(f"empty candidate pool for {key!r}")
        return shuffled(seed_for(key), available)[0]
