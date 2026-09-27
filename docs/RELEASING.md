# Releasing this repository (public + Zenodo DOI)

Checklist for going from "private, work in progress" to "public, citable with a permanent DOI." Steps marked (manual) require logging into GitHub/Zenodo yourself — no CLI here can do these on your behalf.

## 1. Final content check

- [ ] `MSC/msc_manifest.csv`/`.json` regenerated and up to date (`python3 scripts/generate_msc_manifest.py`)
- [ ] `docs/download_guide.md` regenerated against your final video set (`python3 scripts/generate_download_guide.py --videos-dir ...`)
- [ ] `DATASHEET.md` reviewed — especially the excluded-movies list and limitations section
- [ ] `CITATION.cff` — replace the `preferred-citation` placeholder with the actual paper title/authors/venue once published
- [ ] `LICENSE` / `LICENSE-DATA` copyright year/name correct

## 2. Make the GitHub repository public (manual)

GitHub repo settings -> General -> Danger Zone -> "Change visibility" -> Public. This is a one-way-feeling action (technically reversible, but treat it as final) — do this only when you're ready for people to actually see it.

## 3. Connect Zenodo to your GitHub account (manual, one-time)

1. Log into <https://zenodo.org> with your GitHub account (or link GitHub under Zenodo account settings).
2. Go to <https://zenodo.org/account/settings/github/> — you'll see a list of your public GitHub repositories.
3. Find `vivit-seg-datasets` in the list and flip its toggle **on**. (It only appears here once the repo is public — do step 2 first.)

## 4. Cut a GitHub Release (manual — this is what actually triggers Zenodo)

1. On GitHub: repo -> Releases -> "Draft a new release."
2. Tag: `v1.0.0` (or whatever version). Title: something like "MSC v1.0.0 — initial public release."
3. Publish the release.
4. Zenodo picks up the new release automatically (via the webhook enabled in step 3) and mints a DOI within a few minutes — check <https://zenodo.org/account/settings/github/> or your Zenodo uploads page.

## 5. Add the DOI badge back into the repo

Zenodo gives you a Markdown badge snippet on the deposit's page, e.g.:

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
```

Paste that near the top of `README.md`, and cite the DOI (not just the GitHub link) in the paper once available.

## 6. Future updates after the DOI exists

Every new GitHub Release creates a **new DOI version** under the same "concept DOI" (an umbrella that always resolves to the latest version). Cite the specific version DOI for exact reproducibility, or the concept DOI if you want citations to always point at the latest release. No need to redo steps 2-3 for updates — only step 4 (cut a new release) is needed each time.
