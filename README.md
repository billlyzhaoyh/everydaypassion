# everydaypassion

A personal morning ritual: every day, one painting and one poem — plus a short
story or essay and a piece of music — with the story behind each a click away.
Art from open-access museum collections, poetry from the public-domain canon plus
a curated modern library, fiction and essays from Standard Ebooks, recordings from
Wikimedia Commons, and a short grounded reflection on each written by Claude.

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

It fires at login and at 06:00 (or the first wake after, if the Mac was asleep),
and greets you once per calendar day (the CLI guards against re-firing). Without
an exported key the agent uses the key in `.env`. Test it now with
`everydaypassion open --force`.

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
| `seeding` | pure deterministic choice (date → seeded order) |
| `store` | dated packages (freeze-once), seen-IDs, favorites |
| `library` | curated local corpus + offline fallback |
| `builder` | orchestration: generate-if-missing, retry → fallback |
| `sources/` | art (Met, Art Institute of Chicago, Cleveland, SMK, Rijksmuseum, V&A); poems (PoetryDB, Standard Ebooks); stories & essays (Standard Ebooks); music (Wikimedia Commons); Wikipedia facts; Claude reflections |
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
cp -r docs _site   # start from the frozen legacy archive (optional locally)
everydaypassion export --out _site --data data/public --base-url /everydaypassion/
```

Builds today into `data/public/` (the published day as JSON, plus the public
site's own seen log so it never repeats itself), then renders every published
day to `_site/`: `index.html` (newest), `day/<date>.html`, `archive.html`, copied
CC0 / public-domain images and CSS. Published days are frozen; `--rebuild`
regenerates them deliberately. The output is responsive (single fluid column,
`width=device-width`, fluid image, dark/light follows the OS) — reads cleanly on
a laptop and a phone.

`scripts/daily-deploy-pages.yml` (copy it over `.github/workflows/daily.yml`)
runs this at 06:00 UTC daily, commits only the
small `data/public/` JSON, and deploys `_site/` with `actions/deploy-pages` — no
images are committed, so the repo stops growing. `docs/` holds the archive from
before that switch and is copied into the site unchanged. To go live:

1. Add `ANTHROPIC_API_KEY` as a repo **Actions secret**.
2. Settings → **Pages** → Build and deployment → Source: **GitHub Actions**.
3. The site lands at `https://<user>.github.io/everydaypassion/`.

## Content & licensing

Every item carries `source` / `license` / `public_ok`; the public build is the
same generator filtered to `public_ok = true`.

- **Publishable:** the CC0 / public-domain museums (Met, Art Institute, Cleveland,
  SMK and Rijksmuseum — the last two under the Public Domain Mark; Rijksmuseum
  images marked In Copyright are skipped), PoetryDB's public-domain poems,
  Standard Ebooks texts (US public domain, CC0 editions), CC0 or
  rights-holder-dedicated recordings from Commons (Open Goldberg Variations,
  Musopen's Set Chopin Free), and Claude's reflections. The Art Institute's own
  description text is CC BY 4.0 and is credited as such.
- **Private only** (`public_ok: false`): the V&A (personal-use licence), curated
  modern art/poems, and Commons recordings whose "public domain" status rests on
  non-US rules (the wider Musopen category).

Music is streamed from Wikimedia (`preload="none"`), never copied into the site.
See [`data/curated/MODERN_POEMS.md`](data/curated/MODERN_POEMS.md) for how to add
modern poems.

## Checking the sources

```bash
.venv/bin/python scripts/check_sources.py [DATE] [--public]
```

Fetches one item from every source (real network calls, no Claude calls) and
prints OK/FAIL per source — the quickest way to see why a morning fell back to
the curated library. APIs do change under us: The Met retired its v1 search on
2026-10-01, which silently took it out of the rotation until it moved to v1.1.

## Tests

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Pure logic (`seeding`, `store`, `library`, `builder`) is unit-tested; the network/
model sources have fast contract tests with fake HTTP.

## Runtime state

Built packages, cached images, the seen log, and favorites live under
`~/.everydaypassion` (override with `EVERYDAYPASSION_HOME`).
