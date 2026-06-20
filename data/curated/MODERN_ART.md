# Curated modern art

Open-access museum APIs (Met, Art Institute of Chicago, Cleveland) only release
CC0 images for **public-domain** works — roughly pre-1929. Modern and
contemporary art is copyrighted, so there's no free firehose for it (the same
wall as modern poetry). For your **private, single-user** ritual you curate it
here; it's surfaced as a first-class source in the daily rotation.

## How to add a piece

1. Drop the image file into your served images directory:
   `~/.everydaypassion/images/` (override with `EVERYDAYPASSION_HOME`).
2. Append an entry to `artworks_modern.json`, referencing the image by filename:

```json
{
  "source": "curated",
  "license": "© the artist / personal use",
  "public_ok": false,
  "title": "Angelus Novus",
  "artist": "Paul Klee",
  "date": "1920",
  "medium": "Oil transfer and watercolour on paper",
  "ref_id": "klee-angelus-novus",
  "image_path": "klee-angelus-novus.jpg"
}
```

- `public_ok: false` keeps the piece in your personal rotation but excludes it
  from any public website build.
- `ref_id` must be unique (it's how no-repeat tracks the piece).
- `image_path` is just the filename; it resolves to the served images directory.
- **Do not commit the image files** (they're copyrighted) — `~/.everydaypassion`
  is outside the repo, and the metadata here carries no image data.

The rotation reserves a slot for curated modern art each cycle; while this file
is empty, that slot simply falls through to a museum source.
