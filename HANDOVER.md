# Handover: checking and finishing this branch on your laptop

This branch (`claude/cool-franklin-yntvzv`) contains:
- **Code-review fixes:** all 15.
- **Deployment:** GitHub Pages deployed with `actions/deploy-pages` instead of committing images.
- **New sources and sections:** a Rijksmuseum art source, a second poetry source, and two new sections, *Today's story* and *Today's music*.
- **The Met fix:** its old search API was retired on 2026-10-01, so it had been missing from the rotation since.

It was built and tested in a cloud session, but two things could only be finished on a machine with your credentials:

1. **Installing the new workflow file.** The cloud session's GitHub token can't push to `.github/workflows/` because it lacks the `workflow` scope. The file is staged at `scripts/daily-deploy-pages.yml`.
2. **Checking two sources from a normal connection.** Wikimedia Commons (music) rate-limited the cloud IP, and the V&A host wasn't reachable there.

The steps run in order. Steps 1–8 are safe to do before merging, and step 9 is for after merging.

---

## 0. Prerequisites

- macOS with `git`
- [`uv`](https://docs.astral.sh/uv/) (`brew install uv`). It fetches a suitable Python (≥ 3.11) if needed.
- An Anthropic API key

## 1. Get the branch

```bash
cd ~/path/to/everydaypassion
```

```bash
git fetch origin && git switch claude/cool-franklin-yntvzv
```

## 2. Install (pinned by `uv.lock`)

```bash
uv sync --all-extras
```

This creates `.venv/` with the `web`, `llm` and `dev` extras; the LaunchAgent expects that path.

## 3. Configure `.env`

```bash
cp -n .env.example .env
```

Set `ANTHROPIC_API_KEY` in `.env`. Optional settings, all with defaults:

| Variable | Default | What it does |
|---|---|---|
| `EVERYDAYPASSION_MODEL` | `claude-opus-4-8` | Writes the "Read about this" notes |
| `EVERYDAYPASSION_GATE_MODEL` | `claude-haiku-5-5` | The YES/NO poem taste check |
| `EVERYDAYPASSION_CONTACT` | the repo's GitHub URL | Contact info in the User-Agent (Wikimedia may block clients without one) |
| `EVERYDAYPASSION_HOME` | `~/.everydaypassion` | Runtime state (`~` is now expanded) |

## 4. Run the tests

```bash
.venv/bin/pytest -q
```

Expect `76 passed`. No network or API key is needed.

## 5. Check every source from your connection

```bash
.venv/bin/python scripts/check_sources.py
```

```bash
.venv/bin/python scripts/check_sources.py --public
```

Expect `11/11` and `10/10` (the public run leaves out the V&A).

From the cloud session every source passed **except**:
- **Wikimedia Commons (music):** it returned `429 Too Many Requests` to the shared cloud IP. If you see a 429, wait a minute and run again. A `FAIL` that isn't a 429 is a real problem; send me the output.
- **V&A:** its host wasn't allowed there, so it has never been checked against this branch.

## 6. Try a full morning without touching your real archive

```bash
export EVERYDAYPASSION_HOME="$(mktemp -d)"
```

```bash
.venv/bin/everydaypassion build
```

```bash
.venv/bin/everydaypassion serve
```

Open <http://127.0.0.1:7777> and check:

- The artwork and poem render as before.
- **Today's story:** expand "Read it · about N min" and the full text appears.
- **Today's music:** the player plays in Safari too (MP3 versions are preferred).
- Each "✦ Read about this" opens a background note.
- Theme toggle: the audio control and the credit links follow the theme.
- `/day/not-a-date` now returns a 404, and `/archive` keeps working.

When done, press Ctrl-C and run `unset EVERYDAYPASSION_HOME`.

**About your real archive:**
- Days already built stay exactly as they were (frozen). Only new days get a story and music.
- A *new* day that is built incomplete (offline at login, or a failed note) is now retried on later visits instead of being frozen in that state.
- Each new day now costs four note-writing calls (art, poem, story, music) plus up to five small taste checks for the poem.

## 7. Optional: preview the public site locally

```bash
rm -rf _site /tmp/edp-public && cp -r docs _site && cp -r data/public /tmp/edp-public
```

```bash
rm -f "_site/day/$(date +%F).html"
```

```bash
.venv/bin/everydaypassion export --out _site --data /tmp/edp-public --base-url /
```

```bash
python3 -m http.server -d _site 8000
```

What each step does:
- The second command removes today's legacy page from the copy, so today is built with the new code.
- The export uses a *copy* of `data/public`, so the preview doesn't change committed files.
- `--base-url /` is needed because the preview is served at the root.

Then open <http://127.0.0.1:8000/>.

## 8. Reinstall the LaunchAgent

```bash
./scripts/install-launch-agent.sh
```

```bash
ls -l ~/Library/LaunchAgents/com.everydaypassion.open.plist
```

```bash
plutil -p ~/Library/LaunchAgents/com.everydaypassion.open.plist
```

```bash
.venv/bin/everydaypassion open --force
```

Check that:
- The plist is `-rw-------` (only you can read it).
- It has a `StartCalendarInterval` of 06:00. It now runs at login **and** each morning, or at first wake if the Mac was asleep.
- If you didn't export `ANTHROPIC_API_KEY`, there's no `EnvironmentVariables` block, and the agent uses the key in `.env`.

## 9. After merging: switch Pages to the Actions deployment

Your own git credentials can push workflow files.

```bash
git switch main && git pull
```

```bash
grep -v '^# TO INSTALL' scripts/daily-deploy-pages.yml > .github/workflows/daily.yml
```

```bash
git rm -q scripts/daily-deploy-pages.yml
```

```bash
grep -v '^> \*\*Pending:\*\*' README.md > README.tmp && mv README.tmp README.md
```

```bash
git commit -am "Deploy GitHub Pages with actions/deploy-pages"
```

```bash
git push
```

Then on GitHub:

1. Go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
2. Under **Settings → Secrets and variables → Actions**, check that `ANTHROPIC_API_KEY` is still there. Existing pages have notes, so it should be.
3. Go to **Actions → Daily morning → Run workflow**. Both jobs should pass:
   - `build` commits a small "Daily morning: <date>" change under `data/public/`.
   - `deploy` publishes the site.
4. Open the site. Today has a story and music, the archive still lists every old day, and old images still load. The legacy archive in `docs/` is copied in unchanged.

**If something goes wrong:**
- Set the Pages source back to *Deploy from a branch → main → /docs*.
- Undo the workflow change with `git revert <that commit>`.
- The new code also works with the old workflow; you just lose the repo-size benefit.

## 10. First week: what to watch

- **The export step's log** in the workflow run. Warnings such as `missing reflection` or `rebuild still incomplete` mean a source or the API key failed that day.
- **Music on GitHub's runners.** These share IPs, so Commons may rate-limit them too. The code waits once (honouring `Retry-After`, capped at 30 seconds). The workflow builds with `--days 2`, so yesterday is retried the next morning if it was published without music.
- **Repo size.** Growth stops, but the ~30 MB of images already in git history stays. Shrinking it would mean rewriting `main`'s history, which isn't worth it unless the size becomes a problem.

## 11. Not done yet: next candidates

- **Art:** Getty (CC0 Linked Art, no key) and the National Gallery of Art open data.
- **Poetry:** Wikisource. Wikimedia rate-limited the cloud session, but it should work from your laptop or from Actions.
- **Music:** more Commons categories. Add them to `CATEGORIES` in `everydaypassion/sources/commons.py` with the licences that are safe to publish, or `None` for private-only.

## For future cloud sessions

A personal cloud environment named **everydaypassion** now exists. It allows the museum, poetry, Wikipedia and Wikimedia hosts the sources use, but not the V&A's `api.vam.ac.uk`. Pick it when you start a cloud session for this repo so the sources can be reached.
