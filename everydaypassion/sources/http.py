"""Tiny stdlib HTTP helper, injectable so sources test without the network."""

from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path

_UA = "everydaypassion/0.1 (personal morning ritual)"


class Http:
    def __init__(self, timeout: float = 15.0, user_agent: str = _UA, extra_headers: dict | None = None):
        self.timeout = timeout
        self.user_agent = user_agent
        self.extra_headers = extra_headers or {}

    def _headers(self) -> dict:
        return {"User-Agent": self.user_agent, **self.extra_headers}

    def get_json(self, url: str) -> dict:
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)

    def download(self, url: str, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return dest
