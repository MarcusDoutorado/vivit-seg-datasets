#!/usr/bin/env python3
"""Drops shot-pair rows that reference a shot with no visual embedding from
one or more dataset CSVs (produced by 03_build_shot_windows.py).

Reality this handles: a small fraction of shots (~0.8% on MSC historically)
are too short to sample `--frames-per-shot` frames from, so
02_extract_key_frames.py / 07_extract_visual_features.py skip them rather
than aborting the whole run. The dataset CSVs from 03_build_shot_windows.py
don't know this happened, though -- they still contain the pairs that
reference those shots, which would otherwise blow up whatever loads the
(nonexistent) visual embedding at train time. This script removes exactly
those rows.

Rewritten as a clean, idempotent post-processing step from vivit-seg's
experiment_manager/filter_msc_missing_visual.py, which hardcoded
`frames_8` and overwrote the input CSVs in place (with a `.bak` sibling).
Here, `--frames-per-shot` is a required CLI arg, and outputs are always
written to a new path -- inputs are never modified.

Usage:
    python3 scripts/08_filter_missing_visual.py \\
        --dataset-dir /path/to/working/MSC_Dataset \\
        --frames-per-shot 8 \\
        --dataset-csv metadata/dataset_clean_msc_16.csv metadata/dataset_aug_msc_16.csv \\
        --output-dir metadata/filtered
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from msc_pipeline_common import parse_literal, resolve_dataset_dir


def find_missing_shots(shots_csv: Path, frames_root: Path) -> set[tuple[str, str]]:
    shots_df = pd.read_csv(shots_csv)

    by_video: dict[str, list[str]] = {}
    for filename in shots_df["filename"]:
        path = Path(filename)
        by_video.setdefault(path.parent.name, []).append(path.stem)

    missing = set()
    for video, shots in by_video.items():
        frame_dir = frames_root / video
        have = (
            {f.name.split("_")[0] + "_" + f.name.split("_")[1] for f in frame_dir.glob("shot_*.png")}
            if frame_dir.exists()
            else set()
        )
        for shot in shots:
            if shot not in have:
                missing.add((video, shot))
    return missing


def row_has_missing_shot(shots_field, missing: set[tuple[str, str]]) -> bool:
    try:
        paths = parse_literal(shots_field)
    except (ValueError, SyntaxError):
        return False
    return any((Path(p).parent.name, Path(p).stem) in missing for p in paths)


def filter_csv(input_path: Path, output_path: Path, missing: set[tuple[str, str]]):
    df = pd.read_csv(input_path)
    mask = df["shots"].apply(lambda s: row_has_missing_shot(s, missing))
    n_dropped = int(mask.sum())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered = df[~mask]
    filtered.to_csv(output_path, index=False)

    print(
        f"{input_path.name}: {n_dropped}/{len(df)} rows dropped "
        f"(referenced a shot with no visual embedding) -> {len(filtered)} rows written to {output_path}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="Default: <root-dir>/Datasets/MSC_Dataset (see --root-dir).")
    parser.add_argument("--root-dir", type=str, default=None,
                        help="Base directory to derive --dataset-dir from (as <root-dir>/Datasets/MSC_Dataset) when --dataset-dir is not given. "
                             "Falls back to the MSC_ROOT_DIR environment variable, then the current working directory. Ignored if --dataset-dir is given.")
    parser.add_argument("--shots-csv", type=Path, default=None, help="Default: <dataset-dir>/metadata/shots.csv")
    parser.add_argument("--frames-per-shot", type=int, required=True,
                        help="Must match the frames_<N> directory used for visual extraction (e.g. 8 for --num-frames 16 --num-shots 2).")
    parser.add_argument("--dataset-csv", type=Path, nargs="+", required=True,
                        help="One or more dataset CSVs to filter (paths relative to --dataset-dir, or absolute).")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Directory to write filtered CSVs into (same filenames). Default: <dataset-dir>/metadata/filtered/")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    shots_csv = args.shots_csv or (dataset_dir / "metadata" / "shots.csv")
    frames_root = dataset_dir / f"frames_{args.frames_per_shot}"
    output_dir = args.output_dir or (dataset_dir / "metadata" / "filtered")

    missing = find_missing_shots(shots_csv, frames_root)
    print(f"Shots with no visual embedding (frames_{args.frames_per_shot}): {len(missing)}")

    for csv_arg in args.dataset_csv:
        input_path = csv_arg if csv_arg.is_absolute() else (dataset_dir / csv_arg)
        if not input_path.exists():
            print(f"SKIP (not found): {input_path}")
            continue
        output_path = output_dir / input_path.name
        filter_csv(input_path, output_path, missing)


if __name__ == "__main__":
    main()
