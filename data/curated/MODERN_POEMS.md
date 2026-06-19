# Curated modern poetry

The classic, public-domain poems live in `poems.json` with `"public_ok": true`.
Contemporary poems are under copyright. For your **private, single-user** ritual
you can add them here, but they must stay out of any public build.

To add a modern poem, append an entry to `poems.json` with `"public_ok": false`:

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
