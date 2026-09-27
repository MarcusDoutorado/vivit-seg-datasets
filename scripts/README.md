# scripts/

Standalone, CLI-driven scripts to reproduce everything downstream of the
verified MSC groundtruth in `MSC/`: from raw movie files you've sourced
yourself, through per-shot clips, audio/text/visual features, to the
leave-one-video-out (LOVO) training CSVs used in the paper.

These scripts have **no dependency on the companion model repository**
([vivit-seg](https://github.com/Wan-Song/vivit-seg)) -- no `setting.Setting`,
no `DatasetHandler`, no experiment-runner machinery. Everything is plain
argparse CLIs plus two small local helper modules
(`msc_pipeline_common.py`, `feature_extractors.py`). They were ported and
adapted from vivit-seg's `experiment_manager/` and `src/preprocess/` /
`src/datasets/` (see each script's docstring for exactly what changed and
why).

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

System dependency (not installable via pip): the **`ffmpeg`/`ffprobe`**
binaries must be on `PATH`. Used directly by `01_generate_shots.py` and
`04_extract_audio_features.py`, and internally by `openai-whisper`.

A GPU is strongly recommended for `07_extract_visual_features.py` (ViViT
forward passes) and helps `05_transcribe_shots_whisper.py` (Whisper), but
neither requires one -- both fall back to CPU. `google/vivit-b-16x2-kinetics400`
and `sentence-transformers/all-MiniLM-L6-v2` are downloaded from HuggingFace
on first use.

## Dataset directory resolution

Every script below takes `--dataset-dir`, pointing straight at your working
copy of the dataset (where `raw/`, `frames_<N>/`, `metadata/`, `features/`,
`embeddings/` live). If you pass it explicitly, that's exactly what's used --
nothing else in this section applies.

If you omit `--dataset-dir` (e.g. because you keep all your datasets under
one common folder and don't want to spell out the full path every time),
it's derived instead as `<root-dir>/Datasets/MSC_Dataset` -- matching the
layout that `MSC/shots_trust.csv`'s `filename` column implies (e.g.
`Datasets/MSC_Dataset/raw/shots/msc_0005/shot_0001.mp4`). `<root-dir>` is
resolved in this precedence order:

1. The `--root-dir` flag, if given.
2. Else the `MSC_ROOT_DIR` environment variable, if set.
3. Else the current working directory (i.e. running the scripts from a
   directory that itself contains, or will contain, a `Datasets/` folder
   works with zero configuration).

This logic lives in one place (`msc_pipeline_common.py`'s `get_root_dir` /
`default_dataset_dir` / `resolve_dataset_dir`) and every script below just
calls it after parsing its own arguments -- there's nothing dataset-dir- or
root-dir-specific to configure per script beyond those two flags.

## Run order

Steps 1-2 come first and are prerequisites for everything else. Steps 3-7
can then run in any order relative to each other (they're independent
modalities), except that 6 needs 5's output and 8 needs 7's output.

| # | Script | What it produces |
|---|--------|-------------------|
| 1 | `01_generate_shots.py` | Cuts raw movies into `raw/shots/msc_XXXX/shot_NNNN.mp4`; writes `metadata/shots.csv` + `metadata/scenes.csv` |
| 2 | `02_extract_key_frames.py` | Samples PNG key-frames per shot into `frames_<N>/msc_XXXX/` |
| 3 | `03_build_shot_windows.py` | Builds `dataset_{clean,aug}_*.csv` (shot-pair windows, labels, augmentation) and, with `--generate-lovo`, one `dataset_{clean,aug}_*_exclude_<video_id>.csv` per movie |
| 4 | `04_extract_audio_features.py` | MFCC/LogMel raw features + normalized `.pkl` embeddings, per shot |
| 5 | `05_transcribe_shots_whisper.py` | Whisper transcription per shot + a synthetic per-movie SRT (MSC has no official subtitles) |
| 6 | `06_extract_textual_features.py` | sentence-transformers embeddings per shot, from step 5's SRT |
| 7 | `07_extract_visual_features.py` | ViViT visual embeddings per shot, from step 2's key-frames |
| 8 | `08_filter_missing_visual.py` | Drops rows from step 3's CSVs that reference a shot with no visual embedding (from step 7) |

Also present, pre-existing repo-maintenance scripts (not part of the feature
pipeline above): `generate_msc_manifest.py`, `generate_download_guide.py`,
`verify_msc_download.py` -- see the main [README](../README.md) and
[docs/download_guide.md](../docs/download_guide.md).

## Example invocations

These flag values match `setup_msc_dataset_cpu.sh` / `setup_msc_dataset_gpu.sh`,
the shell scripts that ran this pipeline for MSC in vivit-seg
(`--num-frames 16 --num-shots 2 --transition-pos 2`, i.e. 8 real frames
sampled per shot, 2 shots per window).

```bash
DATASET_DIR=/path/to/working/MSC_Dataset   # created by these scripts; NOT the repo checkout

# 1. Cut shots (--videos-dir: your sourced movies, named per MSC/msc_movies.csv's
#    fileName column -- see docs/download_guide.md)
python3 scripts/01_generate_shots.py \
    --videos-dir /path/to/your/msc/videos \
    --dataset-dir "$DATASET_DIR"

# 2. Key-frames (frames-per-shot = num-frames / num-shots = 16/2 = 8)
python3 scripts/02_extract_key_frames.py \
    --dataset-dir "$DATASET_DIR" --frames-per-shot 8

# 3. Shot-pair windows + augmentation + LOVO splits
python3 scripts/03_build_shot_windows.py \
    --dataset-dir "$DATASET_DIR" \
    --num-frames 16 --num-shots 2 --transition-pos 2 \
    --csv-suffix msc --generate-lovo

# 4. Audio (MFCC)
python3 scripts/04_extract_audio_features.py \
    --dataset-dir "$DATASET_DIR" \
    --feature-type mfcc --generate-features --generate-embeddings

# 5. Whisper transcription (MSC has no official subtitles)
python3 scripts/05_transcribe_shots_whisper.py \
    --dataset-dir "$DATASET_DIR" --model base --language en

# 6. Textual embeddings
python3 scripts/06_extract_textual_features.py --dataset-dir "$DATASET_DIR"

# 7. Visual embeddings (ViViT, temporal_mean -- the strategy used for
#    MSC's reported results; GPU recommended)
python3 scripts/07_extract_visual_features.py \
    --dataset-dir "$DATASET_DIR" \
    --num-frames 16 --num-shots 2 --transition-pos 2 \
    --visual-embedding temporal_mean

# 8. Drop rows referencing shots with no visual embedding
#    (~0.8% of MSC shots historically -- too short to sample 8 frames from)
python3 scripts/08_filter_missing_visual.py \
    --dataset-dir "$DATASET_DIR" --frames-per-shot 8 \
    --dataset-csv metadata/dataset_clean_msc_16.csv metadata/dataset_aug_msc_16.csv
```

`--dataset-dir` is a working directory these scripts create and manage
(shots, frames, features, embeddings, metadata CSVs) -- point it wherever
you have room (movie files + shots + frames + embeddings for all 54 movies
add up to a lot of disk). It's independent of your vivit-seg-datasets repo
checkout.

Equivalently, if you'd rather not repeat `--dataset-dir` on every call, set
it once via `--root-dir` or `MSC_ROOT_DIR` and omit `--dataset-dir`
everywhere -- see "Dataset directory resolution" above. For example, with
`export MSC_ROOT_DIR=/path/to/your/workspace`, every command above becomes
`.../workspace/Datasets/MSC_Dataset` without needing `--dataset-dir` at all.

## What was deliberately dropped or changed vs. vivit-seg

Full detail is in each script's own docstring; summary:

- **Legacy visual embedding mode** (`extract_legacy_classifier_input` /
  `visual_embedding_cache.py`) -- not ported. Only the "current" per-shot
  ViViT embedding mode is here.
- **Unimplemented visual-embedding strategy names** (`attention_pool`,
  `cls_residual`, `multi_layer`, `spatial_temporal`, `temporal_mean_std`) --
  vivit-seg lists these but raises `ValueError` if you actually select them
  (no real implementation exists). Not exposed here.
- **`preprocess_features.py`** -- confirmed dead/debug code in vivit-seg
  (hardcoded to one BBC video), fully superseded by
  `extract_visual_features.py`. Not ported.
- **`extract_msc_frames_only.py`** -- not ported as-is (it hacked around
  `DatasetHandler.__init__` via `__new__` + private-attribute injection just
  to reuse its frame-sampling methods). The underlying logic is cleanly
  reimplemented in `02_extract_key_frames.py` instead.
- **`--amount-data`** -- present in vivit-seg's `DatasetHandler`/CLI but
  assigned and never read again anywhere in the class; a dead argument, not
  carried over.
- **Frames-per-shot consistency** -- vivit-seg's `dataset_handler.py`
  hardcodes `versions = [(16, 32)]` for the "indices" column regardless of
  the `--num-frames`/`--num-shots` the frames were actually *extracted*
  with. On MSC this was run with 8 real frames/shot extracted but 16
  sampled into "indices" -- silently repeating each real frame twice
  end-to-end, and confusing enough that a second script + an environment
  variable existed just to produce a consistent 16-frames-per-shot run
  (`experiment_manager/run_msc_16frames.sh`). `03_build_shot_windows.py`
  uses `--num-frames`/`--num-shots` consistently for both extraction and
  sampling, and names output CSVs after the actual configured total instead
  of a hardcoded `_32`.
- **Audio "legacy layout" fallback** (`audio_features/<video>/<shot>_<type>.npy`,
  BBC/OVSD only) -- dropped, irrelevant for this from-scratch pipeline.
- **Hardcoded dataset path if/elif** in `extract_text_from_shots.py`
  (picking one of three fixed `/home/marcus/Research/Datasets/{OVSD,BBC,MSC}_Dataset`
  paths) -- replaced by a plain `--dataset-dir` CLI arg everywhere.
- **`filter_msc_missing_visual.py`** -- rewritten to take
  `--frames-per-shot` as a CLI arg instead of a hardcoded `frames_8`, and to
  write filtered output to a new path rather than overwriting the input
  CSV in place with a `.bak` sibling.
- **`src/preprocess/utils.py`'s `load_shot_frames`** -- dead/buggy (references
  an unimported `cv2`). Not ported.

## Validation

Every script here was smoke-tested end-to-end against `msc_0005` using real
local data (raw movie file, real shot clips, real reference embeddings from
the original vivit-seg run), not just unit-tested in isolation. Where the
original pipeline had already produced a reference output for the same
shot, the ported script's output matched it: identical recomputed shot
frame counts in `shots.csv`, identical `(128, 40)` MFCC embedding
shape/metadata, identical `(384,)` textual embedding shape/metadata, and
identical `(8, 768)` ViViT `temporal_mean` embedding shape/metadata for
`shot_0001`. See the main README's reproduction section for the current
verification status.
