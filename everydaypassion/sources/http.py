"""Tiny stdlib HTTP helper, injectable so sources test without the network."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import __version__

# Wikimedia (and others) may block clients whose User-Agent has no contact
# details. Set EVERYDAYPASSION_CONTACT to a URL or email you're happy to share.
_CONTACT = os.environ.get("EVERYDAYPASSION_CONTACT", "https://github.com/billlyzhaoyh/everydaypassion")
_UA = (
    f"everydaypassion/{__version__} ({_CONTACT}; personal morning ritual) "
    f"Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"
)


class Http:
    def __init__(self, timeout: float = 15.0, user_agent: str = _UA, extra_headers: dict | None = None,
                 max_wait: float = 30.0):
        self.timeout = timeout
        self.max_wait = max_wait
        self.user_agent = user_agent
        self.extra_headers = extra_headers or {}

    def _headers(self) -> dict:
        return {"User-Agent": self.user_agent, **self.extra_headers}

    def _open(self, url: str):
        """urlopen, honouring one 429/503 ``Retry-After`` (capped) before giving up —
        Wikimedia rate-limits shared IPs such as CI runners."""
        req = urllib.request.Request(url, headers=self._headers())
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503):
                raise
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            time.sleep(min(int(retry_after) if retry_after.isdigit() else 5, self.max_wait))
            return urllib.request.urlopen(req, timeout=self.timeout)

    def get_json(self, url: str) -> dict:
        with self._open(url) as resp:
            return json.load(resp)

    def get_text(self, url: str) -> str:
        with self._open(url) as resp:
            return resp.read().decode("utf-8")

    def download(self, url: str, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return dest
