# PRD — everydaypassion

A personal morning art ritual: every day, one painting and one poem, with the story behind them a click away. Inspired by EveryArt and the daily-revisitable cadence of apps like unzoomed.

> "Poetry, beauty, romance, love — these are what we stay alive for." — *Dead Poets Society*

---

## Problem Statement

On workdays I dive straight into work without pausing for anything that feeds me as a person. I want a small, reliable morning ritual — ten minutes of real human art and poetry — that *comes to me* when I sit down at my machine, rather than another app I have to remember to open. It should feel like stepping into a quiet gallery, let me sit with the work first and read about it only if I choose, let me keep the pieces that move me, and let me wander back through past mornings. It must never greet me with a spinner or an error, even if my laptop was off all night or the Wi-Fi is flaky.

## Solution

A local web app on macOS that, on my first login/wake each day, automatically opens a browser tab showing **one artwork and one poem for that calendar day**, presented as a single calm vertical scroll in one of two gallery moods (Museum Dark / Warm Paper, following macOS appearance). The artwork comes from The Met's Open Access collection and the poem from a public-domain corpus or a small curated modern library; a one-click "Read about this" reveals a short, grounded reflection that Claude writes from real Met + Wikipedia facts. Each day's pieces are deterministic for that date, so I can always return to any past morning, mark favorites, and never see a repeat. If a source is unreachable, the app falls back to a curated local library so the ritual always works — even fully offline.

## User Stories

1. As a person starting my day, I want a browser tab to open on its own when I first log in or wake my machine, so that the ritual comes to me without my having to remember it.
2. As a person whose laptop isn't always on at a fixed hour, I want the morning to be tied to "the first time I sit down" rather than a clock time, so that I never miss it because the machine was asleep or off at 6am.
3. As a person who wants the ritual once per day, I want the tab to auto-open only once per calendar day, so that revisiting later in the day doesn't re-trigger it.
4. As a contemplative viewer, I want exactly one artwork and one poem each day, so that I can give singular attention rather than skim a feed.
5. As a viewer, I want the artwork and poem on one quiet vertical scroll, so that the experience feels like one continuous calm moment.
6. As a returning user, I want each calendar date to always resolve to the same artwork and poem, so that "that Tuesday's poem" is a stable thing I can find again.
7. As someone building a habit, I want to revisit any past day's pieces, so that I can return to works that moved me (like flipping back through past days in unzoomed).
8. As a viewer who dislikes reruns, I want the app to avoid showing me artworks/poems it has already shown, so that each morning feels fresh.
9. As an art lover, I want real human-made artwork from a reputable collection (The Met), so that the ritual honours real art rather than machine-generated images.
10. As a viewer, I want the artwork to be consistently contemplation-worthy (paintings, drawings, photographs — not potsherds or coins with no image), so that the daily piece is worth sitting with.
11. As a poetry reader, I want short-but-not-epic poems, so that a poem fits a ten-minute sit rather than becoming a Victorian slog.
12. As a poetry reader, I want low-quality or doggerel poems screened out, so that what I read each morning is genuinely well-crafted.
13. As a reader of contemporary poetry, I want modern poets in the rotation alongside the classics, so that the ritual includes living voices, not only the public-domain canon.
14. As a curious viewer, I want to read a short, warm, accurate reflection about the artwork and artist, so that I understand the background and story of what I'm looking at.
15. As someone who values the unmediated first encounter, I want the reflection hidden behind a single "Read about this" click, so that I form my own reaction before reading the curator's note.
16. As a reader who cares about accuracy, I want the reflection grounded in real facts (Met metadata + Wikipedia), so that it doesn't invent biography about the artist or work.
17. As a person who finds keepers, I want to mark a day's piece as a favorite with a single action, so that I can build a personal collection of works that moved me.
18. As a collector, I want a favorites view, so that I can browse everything I've kept.
19. As a wanderer, I want an archive view of past mornings, so that I can browse the days I've already seen.
20. As a user mid-ritual, I want the page to load instantly with no spinner, so that the calm isn't broken by waiting.
21. As a user on flaky Wi-Fi or fully offline, I want the morning to still show something, so that an outage never robs me of the ritual.
22. As a user, I want a day's pieces to be frozen once first built, so that revisiting a date never silently changes what I saw.
23. As a Mac user, I want the mood to follow my system appearance (dark/light), so that it feels native to my environment without fiddling.
24. As a user with a preference, I want a manual theme toggle that persists, so that I can pin Museum Dark or Warm Paper regardless of system setting.
25. As a reader, I want type set in elegant native macOS faces, so that the poem and titles feel like a printed gallery placard rather than a generic web page.
26. As the operator of my own machine, I want the local server to start when needed and shut itself down when idle, so that nothing lingers in the background.
27. As someone who may want to share this one day, I want every piece tagged with its source and license, so that I can later publish a public version filtered to only publishable content without a rewrite.
28. As a future publisher, I want copyrighted modern poems excluded from any public build automatically, so that publishing can't accidentally infringe.
29. As a user, I want the app to retry a failing source briefly before falling back, so that transient blips don't immediately downgrade my morning.
30. As a user, I want the date and a clear way to reach favorites and past mornings from the daily page, so that navigation is obvious without cluttering the contemplative view.

## Implementation Decisions

**Platform & delivery**
- Local web app on macOS, served by an **on-demand Python (FastAPI) server** that is started by the open-the-tab job and **shuts itself down after idle**. No always-on daemon.
- Auto-open is triggered by **first login/wake of the day via a LaunchAgent**, guarded so it opens at most once per calendar day — *not* a fixed wall-clock time (the laptop may be asleep/off). An optional opportunistic prefetch LaunchAgent may pre-build the day when the machine is awake.

**Daily selection & determinism**
- **DailyPicker** is a pure module: given a date and the candidate pools, it returns a `Selection` (which artwork/poem to use). Seeded by the calendar date so a date always resolves identically. No network or model calls inside it.
- One artwork **and** one poem per day, every day of the week.
- No-repeat is enforced via a **seen-IDs log** in PackageStore; the picker is given the already-seen set and excludes it.

**Content sources (hybrid, real human art)**
- **MetSource** fetches a quality-filtered artwork from The Met Open Access API: `isPublicDomain = true`, has a real `primaryImage`, biased to `isHighlight` and/or visual-art departments (e.g. European Paintings; Drawings & Prints; Photographs; Asian Art). Caches/downloads the image to disk (no per-view hotlinking).
- **PoetrySource** picks from PoetryDB (classic, public domain) with a **≤~30-line cap** and a **Claude taste-gate** that rejects doggerel/dated filler and redraws; or from the curated modern library. Returns a `Poem`.
- **CuratedLibrary** is the on-disk store of curated **modern** poems plus offline-fallback artworks, each tagged `source` / `license` / `public_ok`. Seeded with ~20–30 modern poems initially; grows over time. Doubles as the offline/outage fallback corpus.
- **WikipediaClient** fetches artist/work fact summaries via the free Wikipedia REST API.
- **ReflectionWriter** sends grounded facts (Met metadata + Wikipedia summary) to Claude and returns a short reflection (warm, accurate, ~2–3 short paragraphs). Exactly the artwork reflection is generated per day (poem context optional/secondary). Caps model usage to a small, fixed number of calls per day.

**Orchestration, persistence & resilience**
- **DayBuilder** orchestrates generate-if-missing: on first access of a date, run picker → fetch artwork → fetch poem (with taste-gate) → fetch facts → write reflection → assemble package → persist. It accepts its sources by **dependency injection** so the policy is testable with fakes.
- Resilience policy: **retry a source briefly, then fall back to CuratedLibrary**. The morning always renders, even fully offline.
- **A date is frozen once first built** — DayBuilder/PackageStore never rebuild an existing date, keeping the archive stable even if a date was first built offline.
- **PackageStore** owns all on-disk state: dated package read/write/`has`, the freeze rule, the seen-IDs log, and `favorites.json`. Favorites are recorded via a server POST (durable JSON on disk), not browser localStorage.

**Presentation**
- Single vertical scroll: artwork (with caption: title, artist, date, medium, source/license) first, then the poem, then the "Read about this" reveal (hidden by default, one-click), then a footer with the date, a favorite (♡) action, and links to favorites + past mornings.
- **Two themes**: Museum Dark and Warm Paper, defaulting from `prefers-color-scheme` with a persisted manual toggle. Theme switching is client-side.
- Type uses **native macOS faces** (e.g. Didot for display/titles, Iowan Old Style / Hoefler Text for the poem body, a system sans for captions/meta) — no web-font downloads.

**Publish-later readiness**
- Every content item carries `source`, `license`, and `public_ok`. A future public website build is the **same generator filtered to `public_ok = true`** (Met CC0 artwork + classic public-domain poetry + Claude reflections); curated modern poems (copyrighted) are excluded from public builds. Favorites-as-public (per-visitor accounts) is deferred.

**Prototype-derived shape** — the per-card structure was validated in a design mockup; the daily package resolves to roughly:

```
DayPackage {
  date,                       # calendar date, the deterministic seed
  artwork: { source, license, public_ok, title, artist, date, medium, image_path, met_object_id },
  poem:    { source, license, public_ok, title, author, lines[], year },
  reflection: { text, grounded_in: ["The Met", "Wikipedia"] },
  frozen: true               # never rebuilt once written
}
```

## Testing Decisions

A good test here exercises **external behavior through a module's narrow interface**, not its internals — given inputs (a date, candidate pools, a temp directory, injected fake sources), assert the observable outputs (which selection, what got persisted, whether a rebuild was refused, whether fallback engaged). Tests must not assert on private helpers, file layouts beyond the public contract, or exact model prose.

Modules to unit-test (pure logic and policy):
- **DailyPicker** — determinism (same date → same selection), no-repeat exclusion given a seen set, correct one-artwork-one-poem composition. Pure, no I/O — the prime target.
- **PackageStore** — write-then-read round-trips; the **freeze rule** (an existing date is never overwritten); seen-IDs append/query; favorites add/list. Run against a temp directory.
- **CuratedLibrary** — `get`/`all` over a fixture folder; respects `public_ok` filtering; returns deterministic items for a given seed.
- **DayBuilder** — the **retry→fallback policy** using **injected fake sources**: when a source raises, assert fallback to CuratedLibrary; when all sources succeed, assert the assembled package; assert generate-if-missing builds once and frozen dates are not rebuilt.

Network/model clients (**MetSource, PoetrySource's PoetryDB calls, WikipediaClient, ReflectionWriter**) are **not** unit-tested against live services; cover them with a small number of **contract/fixture tests** (recorded responses / mocked clients) verifying request shape and parsing, so the suite is fast and offline-deterministic.

The **WebApp** gets a light integration test (today renders; favorite POST persists; archive lists). launchd glue is verified manually.

Prior art: none in-repo (greenfield). Follow standard `pytest` conventions — fixtures for temp dirs, fakes injected into DayBuilder, recorded JSON for client contract tests.

## Out of Scope

- **Video art** — deferred to a later version (no clean free API; needs manual curation). v1 is artwork + poem only.
- **Public deployment** of a shareable website — only *readiness* (the `public_ok` tag and filterable generator) is in scope, not the deployment itself.
- **Favorites as multi-user / accounts** — favorites are local single-user JSON only.
- **Auto-show-reflection setting** — reflection is always click-to-reveal in v1; a "show automatically" preference is deferred.
- **Holiday / PTO awareness** — the tab will open every day including holidays; harmless and not handled.
- **AI-generated artwork or AI-generated "modern" poems** — explicitly rejected; only real human art and real poems (classic public-domain or curated modern).
- **Gallery White theme** — dropped in favour of the Museum Dark / Warm Paper pair.

## Further Notes

- **Licensing reality that drives the architecture:** The Met Open Access (CC0), PoetryDB (public domain), and Claude's own reflection prose are all publishable; **only the curated modern poems are copyrighted** and thus private-only. This single fact is why content carries a `public_ok` flag and why the public build is just a filter.
- **Met API etiquette:** cache images and metadata rather than proxying the live API per page view; respect rate limits.
- **Wikipedia attribution:** because reflections are Claude's prose grounded in (not verbatim copies of) Wikipedia facts, verbatim CC BY-SA obligations are avoided; still attribute sources in the reflection footer as good practice.
- **Determinism note:** the date seed gives the unzoomed-style property that "day N" is a fixed, returnable thing; combined with the freeze rule, the archive never mutates.
- **Tech stack:** Python + FastAPI + Jinja templates; standard `pytest`. Requires an Anthropic API key for ReflectionWriter and the poetry taste-gate.
- This PRD was written to `PRD.md` in the repo rather than an issue tracker (no tracker configured for this greenfield project). Run `/setup-matt-pocock-skills` later if you want the issue/triage workflow.
