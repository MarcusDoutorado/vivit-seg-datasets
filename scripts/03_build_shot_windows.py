#!/usr/bin/env python3
"""Builds the shot-pair (or shot-window) continuity/transition dataset CSVs
used for training, including data augmentation and leave-one-video-out
(LOVO) splits.

This is a standalone extraction of the MSC-relevant subset of vivit-seg's
src/datasets/dataset_handler.py (~730 lines, shared BBC/OVSD/MSC machinery
behind a --dataset-name flag, Setting.* constants, and Google-Drive
zip-download fallback none of which apply here). Kept:
  - sliding shot windows of `--num-shots` shots, labelled "related"
    (continuity) or "not related" (transition) depending on whether the
    shot at `--transition-pos` inside the window starts a new scene;
  - data augmentation: the minority class (transitions) is duplicated
    (with a different, deterministic pseudo-random frame-sampling "gap"
    per duplicate) up to parity with the majority class (continuities);
  - the "indices" column: for each shot in each window, which real
    on-disk frame indices (from frames_<N>/, produced by
    02_extract_key_frames.py) to read and how many times to repeat each,
    to reach `--num-frames` total frames for the window;
  - --generate-lovo: one dataset_{clean,aug}_<num_frames>_exclude_<video_id>.csv
    per movie, holding it out entirely (train-on-the-rest split for LOVO
    cross-validation).

Deliberately dropped/changed vs. the original:
  - `--amount-data`, kept in vivit-seg's CLI, is assigned to
    self._amount_data in DatasetHandler.__init__ and never read again
    anywhere in the class -- a dead argument. Not carried over.
  - The original hardcodes `versions = [(16, 32)]` inside
    _generate_multiple_datasets: regardless of the --num-frames/--num-shots
    the class was constructed with (which control the frames_<N> directory
    used for *extraction*), the "indices" column sampled from that directory
    is always built as if frames_per_shot=16/total=32. On MSC this actually
    ran with frames_per_shot=8 extracted (16/2), so 16-per-shot sampling with
    only 8 real frames on disk silently repeated each frame twice --
    confirmed by a second script (run_msc_16frames.sh) that had to
    re-extract a whole separate frames_16/ directory and an env-var
    override just to get a consistent 16-frames-per-shot run. This script
    uses `--num-frames`/`--num-shots` consistently end-to-end (both for
    which frames_<N> directory it reads and for how many frames per shot it
    samples into "indices"), and names output CSVs after the *actual*
    configured total, instead of a hardcoded "_32".

Usage (matches vivit-seg's setup_msc_dataset_cpu.sh for MSC):
    python3 scripts/03_build_shot_windows.py \\
        --dataset-dir /path/to/working/MSC_Dataset \\
        --num-frames 16 --num-shots 2 --transition-pos 2 \\
        --csv-suffix msc --generate-lovo

Requires 01_generate_shots.py and 02_extract_key_frames.py (with a matching
--frames-per-shot = num-frames // num-shots) to have already run.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
from collections import defaultdict
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from msc_pipeline_common import (
    DATA_AUGMENTATION_MAX_ARRAY,
    LABEL_NOT_RELATED,
    LABEL_RELATED,
    RANDOM_STATE,
    natural_key,
    resolve_dataset_dir,
    sample_indices,
    sample_indices_gap,
)


def load_scene_lookup(scenes_csv: Path) -> dict[int, pd.IntervalIndex]:
    scenes_df = pd.read_csv(scenes_csv)
    return {
        int(video): pd.IntervalIndex.from_arrays(g.begin.values, g.end.values, closed="both")
        for video, g in scenes_df.groupby("video", sort=False)
    }


def get_transition_shots(video_id: int, shot_numbers: list[int], scene_lookup: dict[int, pd.IntervalIndex]) -> set:
    """Shots that start a new scene relative to the previous shot in the window."""
    transitions = set()
    intervals = scene_lookup.get(video_id)
    if intervals is None or not shot_numbers:
        return transitions

    prev_scene = intervals.get_indexer([shot_numbers[0]])[0]
    for shot_num in shot_numbers[1:]:
        scene_id = intervals.get_indexer([shot_num])[0]
        if scene_id != prev_scene and scene_id != -1 and prev_scene != -1:
            transitions.add(shot_num)
        prev_scene = scene_id
    return transitions


def build_samples(shots_root: Path, scene_lookup, num_shots: int, transition_pos: int, exclude_videos: set[int]) -> pd.DataFrame:
    rows = []
    for dir_name in sorted(os.listdir(shots_root)):
        shots_dir = shots_root / dir_name
        if not shots_dir.is_dir():
            continue

        try:
            video_id = int(dir_name.split("_")[-1])
        except (IndexError, ValueError):
            continue

        if video_id in exclude_videos:
            continue

        shot_files = sorted(os.listdir(shots_dir), key=natural_key)
        if len(shot_files) < num_shots:
            print(f"Skipping {shots_dir}: only {len(shot_files)} shots available (< {num_shots}).")
            continue

        shot_numbers = [natural_key(f) for f in shot_files]
        transitions = get_transition_shots(video_id, shot_numbers, scene_lookup)

        for start_idx in range(0, len(shot_files) - num_shots + 1):
            window_files = shot_files[start_idx:start_idx + num_shots]
            anchor_global_idx = start_idx + transition_pos - 1
            anchor_shot_num = shot_numbers[anchor_global_idx]

            is_transition = anchor_shot_num in transitions
            rows.append({
                "video": video_id,
                "shots": [str(shots_dir / f) for f in window_files],
                "anchor_shot": anchor_shot_num,
                "transition_shot": anchor_shot_num if is_transition else -1,
                "related": LABEL_NOT_RELATED if is_transition else LABEL_RELATED,
            })

    return pd.DataFrame(rows)


def augment(dataset_df: pd.DataFrame) -> pd.DataFrame:
    dataset_df = dataset_df.copy()
    dataset_df["augmented"] = 0

    related = dataset_df[dataset_df["related"] == 1]
    not_related = dataset_df[dataset_df["related"] == 0]
    target_amount = len(related)

    if len(not_related) == 0:
        print("WARNING: no transition samples available for data augmentation.")
        return dataset_df

    if len(not_related) >= target_amount:
        print("No augmentation needed (transitions already >= continuities).")
        return dataset_df

    difference = target_amount - len(not_related)
    print(f"Data augmentation: duplicating {difference} transition samples to reach parity.")

    extra_rows = []
    for idx in range(difference):
        data = not_related.iloc[idx % len(not_related)].copy()
        data["augmented"] = 1
        extra_rows.append(data)

    dataset_df = pd.concat([dataset_df, pd.DataFrame(extra_rows)], ignore_index=True)
    dataset_df = dataset_df.sort_values(by="shots", key=lambda col: col.str[0])
    return dataset_df


def map_shots_to_frame_indices(shots_csv: Path, frames_root: Path) -> dict[str, list[int]]:
    shots_df = pd.read_csv(shots_csv)
    shot_to_index: dict[str, list[int]] = {}

    for _, row in shots_df.iterrows():
        shot_path = Path(row["filename"])
        video_dir = frames_root / shot_path.parent.name
        shot_stem = shot_path.stem

        if not video_dir.exists():
            shot_to_index[str(shot_path)] = []
            continue

        frame_files = sorted(video_dir.glob(f"{shot_stem}_*.png"))
        indices = []
        for f in frame_files:
            try:
                indices.append(int(f.stem.split("_")[-1]))
            except ValueError:
                continue
        shot_to_index[str(shot_path)] = sorted(indices)

    return shot_to_index


def select_key_frames(dataset_df: pd.DataFrame, shot_to_index: dict, frames_per_shot: int, seed: int, max_gap_pool: int) -> pd.DataFrame:
    dataset_df = dataset_df.copy()
    gap_pool = list(range(max_gap_pool))
    rng = random.Random(seed)

    all_indices = []
    for _, row in dataset_df.iterrows():
        augmented = row.get("augmented", 0)
        frames_idx = []

        if augmented == 0:
            for shot in row["shots"]:
                frame_indices = shot_to_index.get(str(shot), [])
                frames_idx.append(sample_indices(frame_indices, frames_per_shot))
        else:
            gap_pos = rng.randrange(0, len(gap_pool))
            gap = gap_pool.pop(gap_pos)
            for shot in row["shots"]:
                frame_indices = shot_to_index.get(str(shot), [])
                frames_idx.append(sample_indices_gap(frame_indices, max(1, gap), frames_per_shot))

        all_indices.append(frames_idx)

    dataset_df["indices"] = all_indices
    return dataset_df


def generate_lovo_datasets(dataset_df: pd.DataFrame, metadata_dir: Path, prefix: str, total_frames: int):
    videos = sorted(dataset_df["video"].unique())
    for video_id in tqdm(videos, desc=f"LOVO splits ({prefix}_{total_frames})"):
        df_filtered = dataset_df[dataset_df["video"] != video_id]
        output_path = metadata_dir / f"dataset_{prefix}_{total_frames}_exclude_{video_id}.csv"
        df_filtered.to_csv(output_path, index=False)


def save_dataset_csv(dataset_df: pd.DataFrame, metadata_dir: Path, prefix: str, suffix: str, total_frames: int) -> Path:
    if suffix:
        name = f"dataset_{prefix}_{suffix}_{total_frames}.csv"
    else:
        name = f"dataset_{prefix}_{total_frames}.csv"
    out_path = metadata_dir / name
    dataset_df.to_csv(out_path, index=False)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="Default: <root-dir>/Datasets/MSC_Dataset (see --root-dir).")
    parser.add_argument("--root-dir", type=str, default=None,
                        help="Base directory to derive --dataset-dir from (as <root-dir>/Datasets/MSC_Dataset) when --dataset-dir is not given. "
                             "Falls back to the MSC_ROOT_DIR environment variable, then the current working directory. Ignored if --dataset-dir is given.")
    parser.add_argument("--shots-csv", type=Path, default=None, help="Default: <dataset-dir>/metadata/shots.csv")
    parser.add_argument("--scenes-csv", type=Path, default=None, help="Default: <dataset-dir>/metadata/scenes.csv")
    parser.add_argument("--num-frames", type=int, default=16, help="Total frames per window (num-shots x frames-per-shot).")
    parser.add_argument("--num-shots", type=int, default=2, help="Number of shots per sample window.")
    parser.add_argument("--transition-pos", type=int, default=2, help="1-based anchor position inside the window checked for a scene transition.")
    parser.add_argument("--csv-suffix", type=str, default="", help="Suffix for the base dataset CSV names (e.g. 'msc').")
    parser.add_argument("--exclude-videos", type=int, nargs="*", default=[], help="Numeric video ids to exclude entirely from the base dataset.")
    parser.add_argument("--generate-lovo", action="store_true", help="Also generate one dataset_*_exclude_<video_id>.csv per movie.")
    parser.add_argument("--random-seed", type=int, default=RANDOM_STATE)
    parser.add_argument("--max-augmentation-gap-pool", type=int, default=DATA_AUGMENTATION_MAX_ARRAY,
                        help="Pool size to draw each augmented row's frame-sampling 'gap' from (must exceed the number of augmented rows produced).")
    args = parser.parse_args()

    if args.num_shots < 1:
        raise SystemExit("--num-shots must be >= 1")
    if not (1 <= args.transition_pos <= args.num_shots):
        raise SystemExit("--transition-pos must be between 1 and --num-shots")
    if args.num_frames < args.num_shots or args.num_frames % args.num_shots != 0:
        raise SystemExit("--num-frames must be >= --num-shots and divisible by --num-shots")

    frames_per_shot = args.num_frames // args.num_shots

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    metadata_dir = dataset_dir / "metadata"
    shots_root = dataset_dir / "raw" / "shots"
    frames_root = dataset_dir / f"frames_{frames_per_shot}"

    shots_csv = args.shots_csv or (metadata_dir / "shots.csv")
    scenes_csv = args.scenes_csv or (metadata_dir / "scenes.csv")

    if not frames_root.exists():
        raise SystemExit(
            f"{frames_root} does not exist -- run 02_extract_key_frames.py with "
            f"--frames-per-shot {frames_per_shot} first."
        )

    scene_lookup = load_scene_lookup(scenes_csv)

    print(f"Building shot windows | num_shots={args.num_shots} transition_pos={args.transition_pos} frames_per_shot={frames_per_shot}")
    clean_df = build_samples(shots_root, scene_lookup, args.num_shots, args.transition_pos, set(args.exclude_videos))
    print(f"Built {len(clean_df)} windows | related={int((clean_df['related'] == 1).sum())} | not_related={int((clean_df['related'] == 0).sum())}")

    shot_to_index = map_shots_to_frame_indices(shots_csv, frames_root)

    aug_df = augment(clean_df)

    for prefix, df in (("clean", clean_df), ("aug", aug_df)):
        df_with_indices = select_key_frames(df, shot_to_index, frames_per_shot, args.random_seed, args.max_augmentation_gap_pool)
        out_path = save_dataset_csv(df_with_indices, metadata_dir, prefix, args.csv_suffix, args.num_frames)
        print(f"Wrote {len(df_with_indices)} rows to {out_path}")

        if args.generate_lovo:
            generate_lovo_datasets(df_with_indices, metadata_dir, prefix, args.num_frames)


if __name__ == "__main__":
    main()
