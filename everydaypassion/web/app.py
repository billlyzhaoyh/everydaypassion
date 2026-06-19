"""The on-demand server.

Serves today (generate-if-missing), any past day, the archive, and favorites;
records favorites via POST; and shuts itself down after a stretch of idle so
nothing lingers in the background.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import signal
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import config

IDLE_SHUTDOWN_SECONDS = int(os.environ.get("EVERYDAYPASSION_IDLE_SECONDS", "1800"))

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _today() -> str:
    return datetime.date.today().isoformat()


def _pretty(date: str) -> str:
    d = datetime.date.fromisoformat(date)
    return d.strftime("%A · %-d %B %Y")


def create_app(online: bool = True) -> FastAPI:
    app = FastAPI(title="everydaypassion")
    builder = config.make_builder(online=online)
    store = builder.store
    images = config.images_dir()
    images.mkdir(parents=True, exist_ok=True)

    app.mount("/images", StaticFiles(directory=str(images)), name="images")
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    app.state.last_active = time.monotonic()

    def image_url(image_path: str | None) -> str | None:
        if not image_path:
            return None
        p = Path(image_path)
        if p.is_absolute() and images in p.parents:
            return f"/images/{p.name}"
        return image_path  # remote URL fallback

    @app.middleware("http")
    async def _touch(request: Request, call_next):
        app.state.last_active = time.monotonic()
        return await call_next(request)

    def render_day(request: Request, date: str) -> HTMLResponse:
        pkg = builder.ensure(date)
        return _TEMPLATES.TemplateResponse(
            request,
            "day.html",
            {
                "pkg": pkg,
                "date": date,
                "pretty": _pretty(date),
                "image_url": image_url(pkg.artwork.image_path),
                "is_favorite": store.is_favorite(date),
                "is_today": date == _today(),
            },
        )

    @app.get("/", response_class=HTMLResponse)
    def today(request: Request):
        return render_day(request, _today())

    @app.get("/day/{date}", response_class=HTMLResponse)
    def day(request: Request, date: str):
        return render_day(request, date)

    @app.get("/archive", response_class=HTMLResponse)
    def archive(request: Request):
        dates = store.archive()
        return _TEMPLATES.TemplateResponse(
            request,
            "list.html",
            {"title": "Past mornings", "dates": dates, "pretty": _pretty, "store": store},
        )

    @app.get("/favorites", response_class=HTMLResponse)
    def favorites(request: Request):
        dates = sorted(store.favorites(), reverse=True)
        return _TEMPLATES.TemplateResponse(
            request,
            "list.html",
            {"title": "Favorites", "dates": dates, "pretty": _pretty, "store": store},
        )

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
