# everydaypassion

A personal morning ritual: every day, one painting and one poem, with the story
behind them a click away. Art from The Met's Open Access collection, poetry from
the public-domain canon plus a curated modern library, and a short grounded
reflection written by Claude.

> "Poetry, beauty, romance, love — these are what we stay alive for." — *Dead Poets Society*

See [`PRD.md`](PRD.md) for the full design and rationale.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[web,llm]"   # web = FastAPI server; llm = Claude reflections
export ANTHROPIC_API_KEY=sk-ant-...      # for reflections + the poetry taste gate
```

Without the key, the ritual still works — you just won't get the AI reflection
(art and poem render as normal).

## Use

```bash
everydaypassion build [DATE]   # build/fetch a day's package (default: today)
everydaypassion serve          # run the local server at http://127.0.0.1:7777
everydaypassion open           # open today's morning in the browser (once per day)
```

Add `--offline` to any command to use only the curated local library (no network,
no key) — the same path the app falls back to automatically when a source is
unreachable.

## The morning ritual, automatically

Install the LaunchAgent so a tab opens on your first login each day:

```bash
ANTHROPIC_API_KEY=sk-ant-... ./scripts/install-launch-agent.sh
```

It greets you once per calendar day (the CLI guards against re-firing). Test it
now with `everydaypassion open --force`.

## How it works

- **Deterministic per date** — a given date always resolves to the same pair, so
  the archive is stable and you can revisit any past morning.
- **Generate-if-missing** — the first time a date is opened, it's built (fetch +
  reflection) and **frozen**; it's never rebuilt.
- **Resilient** — a failing source retries briefly, then falls back to the
  curated library, so the ritual works even fully offline.
- **Two themes** — Museum Dark / Warm Paper, following your macOS appearance with
  a persisted manual toggle.

## Layout

| Module | Role |
|---|---|
| `seeding`, `picker` | pure deterministic choice (date → selection) |
| `store` | dated packages (freeze-once), seen-IDs, favorites |
| `library` | curated local corpus + offline fallback |
| `builder` | orchestration: generate-if-missing, retry → fallback |
| `sources/` | art (Met, Art Institute of Chicago, Cleveland, SMK, V&A) + PoetryDB, Wikipedia, Claude reflections |
| `web/` | render layer + FastAPI server (today / archive / favorites), idle self-shutdown |
| `static_site` | public static export for GitHub Pages |

## Two shapes, one codebase

A `SiteConfig` selects the mode (see `config.py`):

- **Local (private)** — the whole library: every museum, the V&A, curated modern
  art/poems; an interactive server with favorites; Claude called at build time on
  first visit, then frozen. `everydaypassion serve`.
- **Public (static)** — the publishable CC0-only subset (V&A and curated modern
  exclude themselves), rendered to plain files with no interactive state. The
  Claude reflection is generated **at export time** and baked into the HTML — the
  published artifact carries no API key and makes no runtime calls.

## Publishing to GitHub Pages

```bash
everydaypassion export --out docs --base-url /everydaypassion/ --days 1
```

Writes `docs/index.html` (today), `docs/day/<date>.html`, `docs/archive.html`,
plus copied CC0 images and CSS. The output is responsive (single fluid column,
`width=device-width`, fluid image, dark/light follows the OS) — reads cleanly on
a laptop and a phone.

`.github/workflows/daily.yml` runs this at 06:00 UTC daily and commits `docs/`,
so the archive accumulates. To go live:

1. Add `ANTHROPIC_API_KEY` as a repo **Actions secret**.
2. Settings → **Pages** → Source: *Deploy from a branch* → your default branch, `/docs`.
3. The site lands at `https://<user>.github.io/everydaypassion/`.

## Content & licensing

Every item carries `source` / `license` / `public_ok`. The CC0 museums (Met, Art
Institute, Cleveland, SMK), classic public-domain poetry, and Claude's
reflections are publishable; **the V&A (personal-use license) and curated modern
art/poems are private-only** (`public_ok: false`). The public build is the same
generator filtered to `public_ok = true`. See
[`data/curated/MODERN_POEMS.md`](data/curated/MODERN_POEMS.md) for how to add
modern poems.

## Tests

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Pure logic (`picker`, `store`, `library`, `builder`) is unit-tested; the network/
model sources have fast contract tests with fake HTTP.

## Runtime state

Built packages, cached images, the seen log, and favorites live under
`~/.everydaypassion` (override with `EVERYDAYPASSION_HOME`).
