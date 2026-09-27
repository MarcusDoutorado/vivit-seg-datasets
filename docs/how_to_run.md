# How to run the scripts

A quick, practical guide to every script in `scripts/`: what it's for and how to call it. For the full technical reference (every flag, design decisions, what was changed vs. the original pipeline), see [scripts/README.md](../scripts/README.md).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

You also need `ffmpeg`/`ffprobe` installed and on your `PATH` (used to cut shots and extract audio).

There are two groups of scripts, depending on what you want to do.

## Group 1 — Just checking your own copy of the movies

Use these if you've sourced the 54 movies yourself and want to confirm they match ours, without regenerating any features.

### `generate_msc_manifest.py`
Rebuilds `MSC/msc_manifest.csv`/`.json` from the other CSVs in `MSC/`. You'd only run this if you edited one of its source files — the manifest already in the repo is up to date.
```bash
python3 scripts/generate_msc_manifest.py
```

### `generate_download_guide.py`
Given a folder with your movie files, computes a checksum for each and writes `docs/download_guide.md` + `MSC/msc_checksums.csv`.
```bash
python3 scripts/generate_download_guide.py --videos-dir /path/to/your/movies
```

### `verify_msc_download.py`
The one most people want: checks your movies against our reference and prints a PASS/FAIL report per movie (checksum first, falls back to an `ffprobe` frame-count/fps comparison if the checksum doesn't match exactly — e.g. a different re-encode of the same release).
```bash
python3 scripts/verify_msc_download.py --videos-dir /path/to/your/movies
# add --report-out report.csv to also save the result as a CSV
```

## Group 2 — Regenerating features from scratch

Use these if you want to reproduce the actual shot-level audio/text/visual features used in the paper, starting from the raw movie files. Run in order, 1 through 8. Each one reads what the previous step produced.

All of them take `--dataset-dir`, a working folder (not your repo checkout!) where shots/frames/features get written. If you'd rather not repeat it every time, see "Dataset directory resolution" in `scripts/README.md` for a shortcut (`--root-dir` or `MSC_ROOT_DIR`).

```bash
DATASET_DIR=/path/to/a/working/folder
```

| # | Script | What it does |
|---|--------|---------------|
| 1 | `01_generate_shots.py` | Cuts each movie into its individual shot clips |
| 2 | `02_extract_key_frames.py` | Samples a few key frames (PNG) from each shot |
| 3 | `03_build_shot_windows.py` | Builds the shot-pair training rows (continuity labels, augmentation, LOVO splits) |
| 4 | `04_extract_audio_features.py` | Extracts MFCC/LogMel audio features per shot |
| 5 | `05_transcribe_shots_whisper.py` | Transcribes each shot's dialogue with Whisper (MSC has no official subtitles) |
| 6 | `06_extract_textual_features.py` | Turns step 5's transcripts into sentence embeddings |
| 7 | `07_extract_visual_features.py` | Extracts ViViT visual embeddings from step 2's key frames |
| 8 | `08_filter_missing_visual.py` | Drops the handful of shots too short to have a visual embedding |

```bash
# 1. Cut shots
python3 scripts/01_generate_shots.py \
    --videos-dir /path/to/your/movies --dataset-dir "$DATASET_DIR"

# 2. Key frames (8 frames/shot, matching the paper's setup)
python3 scripts/02_extract_key_frames.py \
    --dataset-dir "$DATASET_DIR" --frames-per-shot 8

# 3. Shot-pair windows + augmentation + LOVO splits
python3 scripts/03_build_shot_windows.py \
    --dataset-dir "$DATASET_DIR" --num-frames 16 --num-shots 2 --transition-pos 2 \
    --csv-suffix msc --generate-lovo

# 4. Audio features (MFCC)
python3 scripts/04_extract_audio_features.py \
    --dataset-dir "$DATASET_DIR" --feature-type mfcc --generate-features --generate-embeddings

# 5. Whisper transcription
python3 scripts/05_transcribe_shots_whisper.py \
    --dataset-dir "$DATASET_DIR" --model base --language en

# 6. Text embeddings
python3 scripts/06_extract_textual_features.py --dataset-dir "$DATASET_DIR"

# 7. Visual embeddings (GPU recommended, but works on CPU)
python3 scripts/07_extract_visual_features.py \
    --dataset-dir "$DATASET_DIR" --num-frames 16 --num-shots 2 --transition-pos 2 \
    --visual-embedding temporal_mean

# 8. Drop shots with no visual embedding
python3 scripts/08_filter_missing_visual.py \
    --dataset-dir "$DATASET_DIR" --frames-per-shot 8 \
    --dataset-csv metadata/dataset_clean_msc_16.csv metadata/dataset_aug_msc_16.csv
```

That's it — after step 8 you have the same shot-level features (audio, text, visual) and training CSVs used in our experiments, ready to plug into a model.

Every flag above has a `--help` if you want to see the full list of options for a script (`python3 scripts/03_build_shot_windows.py --help`).
