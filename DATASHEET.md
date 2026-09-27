# Datasheet for MSC (MovieScenes Curated)

Following the framework of Gebru et al., ["Datasheets for Datasets"](https://arxiv.org/abs/1803.09010) (2018/2021).

This datasheet documents the annotation/curation artifacts distributed in this repository, not a redistributed copy of the underlying movies (which we do not distribute — see [Distribution](#distribution)).

## Motivation

**For what purpose was the dataset created?**
MSC curates the 64-movie test split originally released by MovieScenes (Rao et al., CVPR 2020) into a 54-movie subset whose official shot/scene groundtruth we could verify frame-for-frame against an independently-sourced copy of each movie. It was created because applying frame-indexed groundtruth to a video release the annotators didn't use is not guaranteed to align, and we needed a benchmark we could trust was correctly aligned for our own multimodal scene-segmentation experiments.

**Who created this dataset and on whose behalf?**
Marcus Doutorado, as part of graduate research (advisor-supervised) on multimodal movie scene segmentation. The underlying shot/scene annotations originate from MovieScenes/MovieNet (Rao et al. 2020; Huang et al., ECCV 2020) — MSC is a verified, curated derivative, not an independent annotation effort.

**Who funded the creation of the dataset?**
No dedicated external funding for this curation step; produced as part of ongoing graduate research.

## Composition

**What do the instances represent?**
Each instance is a movie from the MovieScenes 64-movie test split. For each of the 54 verified movies, the dataset provides: shot boundaries (frame indices), scene boundaries (frame indices), the specific commercial release (BBFC-classified) our reference copy corresponds to, and 3 low-resolution spot-check frames.

**How many instances are there?**
64 movies total in the original split; 54 in the verified MSC-trust subset used throughout our experiments (see `msc.csv`, `msc_movies.csv`, `msc_manifest.csv`). The 10 excluded movies are listed with their exclusion reason in `excluded_videos.csv`.

**Does the dataset contain all possible instances, or a sample?**
All 64 movies of MovieScenes' official test split were considered; 54 passed verification. This is not a further subsample — it's the full split minus the 10 that could not be reconciled (see [Preprocessing](#preprocessingcleaninglabeling)).

**What data does each instance consist of?**
- Shot/scene frame-index boundaries (`shots.csv`, `scenes.csv`, and the trust-filtered `shots_trust.csv`, `scenes_trust.csv`)
- Movie identifiers: IMDb ID, title, year, genres, runtime (`msc_movies.csv`)
- Per-movie verification metadata: frame offsets applied during reconciliation, verification outcome (`msc_gt_adjust.csv`)
- Per-movie BBFC release match: which specific commercial release (cinema/home-entertainment/other, with runtime to the second) our reference copy's frame count corresponds to, and the reasoning (`msc_frames_bbfc.csv`, `table_msc_dataset_info.csv`)
- Per-movie ffprobe measurements of our own reference copy (frame rate, frame count, duration) (`msc_ffprobe_verification.csv`)
- 3 low-resolution (480px-wide) sample frames per movie for spot-checking (`verification_frames/`)
- A consolidated manifest joining the above into one row per movie (`msc_manifest.csv` / `.json`)

We do **not** include the source video files themselves.

**Is there a label or target associated with each instance?**
Shot and scene boundaries are themselves the annotation (ground truth for the scene-segmentation task); there is no separate class label.

**Is any information missing from individual instances?**
For 4 of the 54 movies (marked `*` in `table_msc_dataset_info.csv`), our reference copy's frame count doesn't fall within 30 seconds of any single BBFC-classified release; the closest available release is reported regardless, as the best available reference — see `msc_frames_bbfc.csv` for the per-movie reasoning.

**Are relationships between individual instances made explicit?**
Each movie is identified consistently across all files by `msc_id` (e.g. `MSC_0005`) and `imdb_id` (e.g. `tt2024544`); `msc_manifest.csv` is the single join point.

**Are there recommended data splits?**
MSC is used as a single evaluation split (a curated version of MovieScenes' own test split), not divided into train/val/test — it's a benchmark for models trained on other data (as in the original MovieScenes protocol).

**Are there any errors, sources of noise, or redundancies?**
The 10 excluded movies (`excluded_videos.csv`) had groundtruth-to-video discrepancies we could not reconcile with a fixed frame offset; rather than construct new unofficial annotations for them, we excluded them. `shots.csv`/`scenes.csv` (all 64 movies, unverified) are kept alongside `shots_trust.csv`/`scenes_trust.csv` (54 movies, verified) for transparency about what was filtered and why.

**Does the dataset rely on external resources?**
Yes — the underlying video files (not distributed, copyright), the MovieScenes/MovieNet groundtruth (external, cited), and BBFC (bbfc.co.uk) classification records (external, used only to identify which release a runtime corresponds to; not archived here beyond the runtime figure and our reasoning).

**Does the dataset contain data that might be considered confidential, or offensive/insulting/threatening?**
No. It contains movie metadata (titles, IMDb IDs, runtimes) and frame-index annotations only. `verification_frames/` contains single frames from commercially-released, publicly-available films — see [Distribution](#distribution) for the fair-use rationale.

## Collection process

**How was the data associated with each instance acquired?**
Shot/scene boundaries: taken directly from MovieScenes' official release (not re-annotated). Movie metadata: from IMDb (title, year, genres, runtime) via each movie's IMDb ID. BBFC release matching: BBFC's public classification records, cross-referenced against `ffprobe` measurements of our own copy of each movie (independently sourced by us, one copy per movie).

**What mechanisms were used?**
Manual verification (comparing groundtruth frame boundaries against the actual video content for each of the 64 movies) plus scripted cross-checks (`ffprobe` for frame counts/rates, BBFC runtime lookup). See `docs/methodology.md` for the full protocol.

**Over what timeframe was the data collected?**
Curation and verification were carried out during 2026 as part of the associated paper's development.

## Preprocessing/cleaning/labeling

**Was any preprocessing/cleaning/labeling done?**
Yes: for each of the 64 movies, official groundtruth was checked against the actual video content. Where a small, consistent start/end frame offset was found, it was reconciled and logged (`msc_gt_adjust.csv`: `frames_start`/`frames_end`). Where no reconciliation was possible — no correspondence at all, or desynchronization too severe/inconsistent to correct with a fixed offset — the movie was excluded (10 of 64; `excluded_videos.csv` gives the specific issue per movie) rather than re-annotated, to avoid defining new, unofficial annotations that no other work could reproduce or verify. Separately, for the 54 verified movies, our own copy's frame count was matched against BBFC-classified release runtimes to identify which specific commercial release it corresponds to (`msc_frames_bbfc.csv`).

**Is the raw data (prior to preprocessing/cleaning/labeling) available?**
`shots.csv`/`scenes.csv` (all 64 movies, before trust-filtering) are the "raw" MovieScenes groundtruth as originally sourced; `msc_gt_adjust.csv` documents every reconciliation applied. Nothing is silently altered — every offset is logged per movie.

## Uses

**Has the dataset been used for any tasks already?**
Yes — it is the benchmark used throughout our multimodal (visual/audio/text) movie scene segmentation paper and thesis work.

**Is there anything about the composition/collection/preprocessing that might impact future uses?**
The 10 excluded movies mean MSC is not a strict subset benchmark of the original 64-movie MovieScenes test split — results on MSC-trust are not directly comparable to results reported on the full 64-movie split by other work unless that work also restricts to the same 54 movies. Because the specific release matched per movie (`msc_frames_bbfc.csv`) may differ from the release another researcher sources independently, frame-exact alignment should be spot-checked via `verification_frames/` before assuming compatibility, particularly for the 4 movies marked `*`.

**Are there tasks for which the dataset should not be used?**
It should not be used as a general movie-metadata or filmography source — IMDb/BBFC fields are included only to support source-verification, not as a curated catalog in their own right.

## Distribution

**Will the dataset be distributed to third parties?**
Yes, publicly, via this repository.

**How will the dataset be distributed?**
As annotation/metadata files (CSV/JSON) plus a small number of low-resolution single-frame images (`verification_frames/`), under the licenses in [`LICENSE`](LICENSE) (code, MIT) and [`LICENSE-DATA`](LICENSE-DATA) (annotations/metadata, CC-BY 4.0). Source videos are never distributed.

**Copyright note on `verification_frames/`.**
These are commercially-copyrighted studio films. We include at most 3 frames per movie, at low resolution (480px-wide), each a single still from within one shot rather than any continuous footage — kept deliberately minimal and used solely to let someone who has independently and legitimately sourced a copy confirm alignment with our shot/scene boundaries, consistent with standard academic fair-use practice for dataset-verification material. If a rights holder objects to a specific frame's inclusion, please open an issue and it will be removed.

## Maintenance

**Who will support/host/maintain the dataset?**
Marcus Doutorado, via this GitHub repository.

**How can others contribute?**
Via GitHub issues/pull requests — in particular, reports of a groundtruth/video mismatch on a specific movie, or a verified release match we should add to `msc_frames_bbfc.csv`, are welcome.
