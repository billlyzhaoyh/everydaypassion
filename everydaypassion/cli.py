"""Command line entry points: build, serve, open."""

from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
import time
import urllib.request
import webbrowser

from . import config

DEFAULT_PORT = 7777


def _url(port: int) -> str:
    return f"http://127.0.0.1:{port}/"


def _server_up(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1):
            return True
    except Exception:
        return False


def cmd_build(args) -> int:
    date = args.date or datetime.date.today().isoformat()
    builder = config.make_builder(online=not args.offline)
    pkg = builder.ensure(date)
    print(f"{date}: {pkg.artwork.title} — {pkg.artwork.artist}")
    print(f"         poem: {pkg.poem.title} — {pkg.poem.author}")
    print(f"         reflections: artwork={'yes' if pkg.artwork_reflection else 'no'}"
          f" poem={'yes' if pkg.poem_reflection else 'no'}")
    return 0


def cmd_export(args) -> int:
    from . import static_site

    site = config.public_site(args.base_url)
    warnings = static_site.export(args.out, site, days=args.days, online=not args.offline)
    print(f"Exported {args.days} day(s) to {args.out} (base {site.base_url})")
    for w in warnings:
        print(f"  warning: {w}")
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    from .web.app import create_app

    app = create_app(online=not args.offline)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def cmd_open(args) -> int:
    # Once-per-day guard so login triggers don't reopen the tab all day.
    today = datetime.date.today().isoformat()
    marker = config.home() / "last_open"
    config.home().mkdir(parents=True, exist_ok=True)
    if not args.force and marker.exists() and marker.read_text().strip() == today:
        print("Already greeted today.")
        return 0

    if not _server_up(args.port):
        subprocess.Popen(
            [sys.executable, "-m", "everydaypassion", "serve", "--port", str(args.port)]
            + (["--offline"] if args.offline else []),
            start_new_session=True,
        )
        for _ in range(40):
            if _server_up(args.port):
                break
            time.sleep(0.25)

    marker.write_text(today)
    webbrowser.open(_url(args.port))
    print(f"Opened {_url(args.port)}")
    return 0


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--offline", action="store_true", help="Use only the curated local library.")
    common.add_argument("--port", type=int, default=DEFAULT_PORT)

    parser = argparse.ArgumentParser(
        prog="everydaypassion", description="A daily art & poetry ritual.", parents=[common]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", parents=[common], help="Build (or fetch) a day's package.")
    p_build.add_argument("date", nargs="?", help="ISO date; defaults to today.")
    p_build.set_defaults(func=cmd_build)

    sub.add_parser("serve", parents=[common], help="Run the local server.").set_defaults(func=cmd_serve)

    p_export = sub.add_parser("export", parents=[common], help="Export the public static site for GitHub Pages.")
    p_export.add_argument("--out", default="docs", help="Output directory (default: docs).")
    p_export.add_argument("--base-url", default="/everydaypassion/", help="Site base path for assets/links.")
    p_export.add_argument("--days", type=int, default=1, help="How many recent days to build (default: today only).")
    p_export.set_defaults(func=cmd_export)

    p_open = sub.add_parser("open", parents=[common], help="Open today's morning in the browser (once per day).")
    p_open.add_argument("--force", action="store_true", help="Open even if already greeted today.")
    p_open.set_defaults(func=cmd_open)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
