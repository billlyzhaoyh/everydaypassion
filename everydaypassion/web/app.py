"""The on-demand server.

Serves today (generate-if-missing), any past day, the archive, and favorites;
records favorites via POST; and shuts itself down after a stretch of idle so
nothing lingers in the background.
"""

from __future__ import annotations

import asyncio
import os
import signal
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import config
from ..config import LOCAL, SiteConfig
from . import render

IDLE_SHUTDOWN_SECONDS = int(os.environ.get("EVERYDAYPASSION_IDLE_SECONDS", "1800"))

_today = render.today
_pretty = render.pretty


def create_app(online: bool = True, site: SiteConfig = LOCAL) -> FastAPI:
    app = FastAPI(title="everydaypassion")
    builder = config.make_builder(online=online, public_only=site.public_only)
    store = builder.store
    images = config.images_dir()
    images.mkdir(parents=True, exist_ok=True)

    app.mount("/images", StaticFiles(directory=str(images)), name="images")
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    app.state.last_active = time.monotonic()

    @app.middleware("http")
    async def _touch(request: Request, call_next):
        app.state.last_active = time.monotonic()
        return await call_next(request)

    def day_html(date: str) -> HTMLResponse:
        pkg = builder.ensure(date)
        html = render.render_day(
            pkg, site=site, date=date, pretty=_pretty(date),
            image_url=render.image_url(site, pkg.artwork.image_path, images),
            is_favorite=store.is_favorite(date), is_today=date == _today(),
        )
        return HTMLResponse(html)

    @app.get("/", response_class=HTMLResponse)
    def today():
        return day_html(_today())

    @app.get("/day/{date}", response_class=HTMLResponse)
    def day(date: str):
        return day_html(date)

    @app.get("/archive", response_class=HTMLResponse)
    def archive():
        html = render.render_list(
            site=site, title="Past mornings", dates=store.archive(),
            pretty=_pretty, is_favorite=store.is_favorite,
        )
        return HTMLResponse(html)

    @app.get("/favorites", response_class=HTMLResponse)
    def favorites():
        html = render.render_list(
            site=site, title="Favorites", dates=sorted(store.favorites(), reverse=True),
            pretty=_pretty, is_favorite=store.is_favorite,
        )
        return HTMLResponse(html)

    @app.post("/favorite/{date}")
    def favorite(date: str):
        return JSONResponse({"favorited": store.toggle_favorite(date)})

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.on_event("startup")
    async def _idle_watch():
        async def loop():
            while True:
                await asyncio.sleep(60)
                if time.monotonic() - app.state.last_active > IDLE_SHUTDOWN_SECONDS:
                    os.kill(os.getpid(), signal.SIGTERM)
                    return

        app.state.idle_task = asyncio.create_task(loop())

    return app
