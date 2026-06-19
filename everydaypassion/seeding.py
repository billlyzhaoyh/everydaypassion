"""Deterministic, dependency-free seeding helpers.

The whole app hangs on one property: a given calendar date always resolves to
the same pieces. These helpers are pure — no global random state, no clock —
so determinism is total and trivially testable.
"""

from __future__ import annotations

import hashlib
from typing import Iterable

_MASK64 = (1 << 64) - 1


def seed_for(key: str) -> int:
    """Map any string key to a stable 64-bit seed."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def shuffled(seed: int, items: Iterable) -> list:
    """Return a deterministic permutation of ``items`` for ``seed``.

    Uses a self-contained LCG-driven Fisher-Yates so the result depends only on
    the seed and the input order — never on Python's global RNG.
    """
    out = list(items)
    state = seed or 1
    for i in range(len(out) - 1, 0, -1):
        state = (state * 6364136223846793005 + 1442695040888963407) & _MASK64
        j = state % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out
