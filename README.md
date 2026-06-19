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
| `sources/` | The Met, PoetryDB, Wikipedia, Claude reflections |
| `web/` | FastAPI server (today / archive / favorites), idle self-shutdown |

## Content & licensing

Every item carries `source` / `license` / `public_ok`. The Met (CC0), classic
public-domain poetry, and Claude's reflections are publishable; **curated modern
poems are copyrighted and private-only** (`public_ok: false`). A future public
build is the same generator filtered to `public_ok = true`. See
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
