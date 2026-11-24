"""TasteGate — the optional model screen shared by the poetry sources.

Each check is a model request, so calls are capped per date and verdicts cached by
ref: a retry (or rebuild) of the same date resumes the spent budget and reuses
verdicts, so it neither pays again nor re-rolls the pick.
"""

from __future__ import annotations

from typing import Callable


class TasteGate:
    def __init__(self, gate: Callable[[list[str]], bool] | None, max_calls: int = 5):
        self.gate = gate
        self.max_calls = max_calls
        self._verdicts: dict[str, bool] = {}
        self._spent: dict[str, int] = {}

    def allows(self, date: str, ref: str, lines: list[str]) -> bool:
        """False only when the gate explicitly rejected ``ref``. No gate, a spent
        budget, or a broken gate all let the poem through."""
        verdict = self._verdicts.get(ref)
        if verdict is None and self.gate is not None and self._spent.get(date, 0) < self.max_calls:
            self._spent[date] = self._spent.get(date, 0) + 1
            screened = [ln for ln in lines if ln.strip()] or lines
            try:
                verdict = bool(self.gate(screened))
            except Exception:  # noqa: BLE001 — a broken screener must not cost the poem
                verdict = True
            self._verdicts[ref] = verdict
        return verdict is not False
