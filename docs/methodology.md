# Methodology

## Path convention: how to resolve `filename` columns

The `filename` column in `shots.csv`/`shots_trust.csv` stores each shot clip's path relative to a root directory, e.g. `Datasets/MSC_Dataset/raw/shots/msc_0005/shot_0001.mp4`. On our own machine that root happens to be a fixed local folder, but any script in this repository (or in the companion `vivit-seg` pipeline) that needs to resolve these into real files supports a configurable root directory, resolved in this order:

1. An explicit `--root-dir` CLI argument, if given.
2. Else the `MSC_ROOT_DIR` environment variable, if set.
3. Else the current working directory (i.e. running the script from a directory that already contains, or will contain, a `Datasets/` folder works with zero configuration).

The real path is then `root_dir / filename_column_value` — e.g. with `root_dir=/data/research`, `Datasets/MSC_Dataset/raw/shots/msc_0005/shot_0001.mp4` resolves to `/data/research/Datasets/MSC_Dataset/raw/shots/msc_0005/shot_0001.mp4`. This lets someone whose own `Datasets/` folder lives somewhere else point at it without editing any CSV.

## Frame provenance: where "Frames" comes from

The "Frames" figures in `shots.csv`/`shots_trust.csv` come directly from MovieScenes' official groundtruth, which is already frame-indexed (`begin`/`end`) — no conversion on our side. We deliberately do not derive frame counts or durations from the video files themselves (e.g. via `ffprobe`): checking our own downloaded copies against the groundtruth's implied frame count showed large, inconsistent discrepancies from movie to movie (not explained by frame-rate differences, which measured consistently at ~23.976fps across the set) — almost certainly because the specific release we sourced doesn't correspond frame-for-frame to whatever copy MovieScenes originally annotated. This is exactly the kind of discrepancy `verification_frames/` (below) and the BBFC cross-check are meant to help catch.

## MSC-trust verification protocol

MovieScenes distributes scene-boundary annotations for a 64-movie test split, but not the raw video files (copyright) — researchers must independently source each movie. Because different releases of the same movie can differ in frame rate, cut (theatrical vs. extended), or included studio logos/idents, applying MovieScenes' frame-indexed groundtruth directly to an independently-sourced copy is not guaranteed to align.

For every one of the 64 movies, we verified the official groundtruth against the specific video file we sourced:

1. Movie located and downloaded via its IMDb identifier (`msc_movies.csv`).
2. Official scene/shot frame boundaries checked against the actual video content.
3. Where small, consistent start/end offsets were found, they were reconciled (logged per-movie in `msc_gt_adjust.csv`: `frames_start` / `frames_end` columns — the frame offset applied at the start/end of the affected boundary).
4. Where no reconciliation was possible — no correspondence to the video at all, or desynchronization too severe/inconsistent to correct with a fixed offset — the movie was excluded rather than re-annotated. We deliberately chose not to construct our own groundtruth for these cases: doing so would define a new, unofficial annotation that no other work could reproduce or verify against the original MovieScenes release. **10 of 64 movies were excluded** this way; see `excluded_videos.csv` for the specific issue identified in each.

The remaining **54 movies** (`shots_trust.csv`, `scenes_trust.csv`) are MSC — the verified benchmark used throughout our experiments.

## BBFC cross-check: identifying which release each movie's frame count corresponds to

The frame counts in `shots.csv`/`shots_trust.csv` come directly from MovieScenes' official groundtruth, but that annotation doesn't disclose which specific commercial release (theatrical, home-entertainment, regional, extended cut, etc.) its annotators used. To identify it, for every one of the 54 verified movies we:

1. Measured the exact frame count of our own downloaded copy directly, via `ffprobe` (independent of the groundtruth annotation).
2. Looked up every release of that movie classified by the BBFC (British Board of Film Classification) — which rates UK theatrical and home-entertainment releases individually, with runtime reported to the second — and converted each candidate runtime to a frame count at 24fps.
3. Matched our `ffprobe`-measured frame count against the closest BBFC-implied frame count, to identify which specific release our copy corresponds to.

This is what populates the Duration and Version columns of `table_msc_dataset_info.csv` (see below), replacing the earlier IMDb-derived, rounded-to-the-minute duration figure. For 50 of 54 movies, the match is within 30 seconds; the remaining 4 differ by more (likely a cut or regional release not separately catalogued by the BBFC) and are marked `*`, reporting the closest available release regardless. `msc_frames_bbfc.csv` documents the full research behind this (every BBFC release found per movie, and the reasoning for the match chosen). This process does not touch `shots.csv`/`shots_trust.csv`/`scenes.csv`/`scenes_trust.csv` — those remain exactly as MovieScenes provided them, per the reproducibility rationale above; only the summary duration/version figures were affected.

## Verification frames

`verification_frames/` contains 3 low-resolution (480px-wide) frames per movie (54 movies × 3 = 162), each from a shot at roughly 15%, 50%, and 85% through that movie's shot list — so that someone who has independently sourced the same movie can extract the same frame from their own copy and visually confirm they have a matching or compatible release, without us needing to redistribute the source video.

Naming convention: `<msc_id>_<shot_file>_frame_<NNN>.jpg`, e.g. `msc_0005_shot_0110_frame_015.jpg` = movie id 5 (12 Years a Slave), `shot_0110.mp4`, frame index 15 within that shot. See `verification_frames/README.md` for the full index (movie ↔ file).

These are commercially-copyrighted studio films (e.g. *The Godfather*, *Inception*) — kept deliberately few (3 per movie), low-resolution, and cropped to a single frame from within a shot rather than any continuous footage, in line with standard academic fair-use practice for dataset verification material.
