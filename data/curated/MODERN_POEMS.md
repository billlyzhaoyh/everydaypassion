# Curated modern poetry

`poems.json` holds classic, public-domain poems (`"public_ok": true`) used as the
offline fallback. Contemporary poems are under copyright; they live in
`poems_modern.json` (`"public_ok": false`) and are surfaced as a first-class
source in the daily rotation. They must stay out of any public build.

To add a modern poem, append an entry to `poems_modern.json`:

```json
{
  "source": "curated",
  "license": "© <poet / publisher>",
  "public_ok": false,
  "title": "<title>",
  "author": "<poet>",
  "year": "<year>",
  "lines": ["<line>", "<line>", "..."]
}
```

- `public_ok: false` keeps the poem in your personal rotation but excludes it
  from any public website build (run with `--public-only` semantics).
- Do **not** publish copyrighted poems. Personal, non-redistributed use only.
- Seed ~20–30 to start; the rotation grows as you add more.
