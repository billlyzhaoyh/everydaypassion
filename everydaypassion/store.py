"""PackageStore — all on-disk state for the ritual.

Owns dated packages (with the freeze-once rule), the seen-IDs log, and
favorites. Pure file I/O over a directory, so it tests cleanly against tmp.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import DayPackage


class PackageStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.packages = self.root / "packages"
        self.packages.mkdir(parents=True, exist_ok=True)
        self.seen_path = self.root / "seen.json"
        self.fav_path = self.root / "favorites.json"

    # ---- dated packages -------------------------------------------------
    def _pkg_path(self, date: str) -> Path:
        return self.packages / f"{date}.json"

    def has(self, date: str) -> bool:
        return self._pkg_path(date).exists()

    def read(self, date: str) -> DayPackage:
        with open(self._pkg_path(date), encoding="utf-8") as f:
            return DayPackage.from_dict(json.load(f))

    def write(self, pkg: DayPackage, overwrite: bool = False) -> bool:
        """Persist a package. A date is frozen once built: an existing date is
        never silently overwritten unless ``overwrite`` is explicit. Returns
        True if written, False if the freeze rule refused it."""
        if self.has(pkg.date) and not overwrite:
            return False
        with open(self._pkg_path(pkg.date), "w", encoding="utf-8") as f:
            json.dump(pkg.to_dict(), f, indent=2, ensure_ascii=False)
        return True

    def archive(self) -> list[str]:
        return sorted((p.stem for p in self.packages.glob("*.json")), reverse=True)

    # ---- seen-IDs log ---------------------------------------------------
    def seen_ids(self) -> set[str]:
        return set(self._load(self.seen_path, []))

    def mark_seen(self, *ids: str) -> None:
        seen = self.seen_ids()
        seen.update(str(i) for i in ids if i)
        self._dump(self.seen_path, sorted(seen))

    # ---- favorites ------------------------------------------------------
    def favorites(self) -> list[str]:
        return list(self._load(self.fav_path, []))

    def is_favorite(self, date: str) -> bool:
        return date in self.favorites()

    def add_favorite(self, date: str) -> None:
        favs = self.favorites()
        if date not in favs:
            favs.append(date)
            self._dump(self.fav_path, favs)

    def remove_favorite(self, date: str) -> None:
        self._dump(self.fav_path, [d for d in self.favorites() if d != date])

    def toggle_favorite(self, date: str) -> bool:
        if self.is_favorite(date):
            self.remove_favorite(date)
            return False
        self.add_favorite(date)
        return True

    # ---- helpers --------------------------------------------------------
    @staticmethod
    def _load(path: Path, default):
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return default

    @staticmethod
    def _dump(path: Path, value) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
