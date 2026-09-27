#!/usr/bin/env python3
"""Extracts a fixed number of uniformly-sampled PNG key-frames per shot.

Reimplements (cleanly, standalone) the frame-sampling logic that lived in
vivit-seg's src/datasets/dataset_handler.py (`_save_key_frames` /
`sample_indices`) -- NOT vivit-seg's experiment_manager/extract_msc_frames_only.py,
which reused that logic by hacking around DatasetHandler.__init__ via
__new__ + private-attribute injection just to call its methods; not worth
carrying that over when the logic itself is ~70 lines.

For every shot in metadata/shots.csv, samples `--frames-per-shot` frame
indices evenly spaced across the shot's real length (via PyAV), resizes each
to VIVIT_IMAGE_SIZE (224x224, ViViT's expected input resolution), and saves
it as frames_<N>/<msc_id>/<shot_stem>_<frame_idx:06d>.png. Idempotent: shots
whose frame directory already has the expected files are skipped unless
--force is given.

The frames_<N> directory is later read by:
  - 03_build_shot_windows.py (to know which real frame indices exist per
    shot when building the "indices" column of the dataset CSVs)
  - 07_extract_visual_features.py (to load the actual pixels for ViViT)

Usage:
    python3 scripts/02_extract_key_frames.py \\
        --dataset-dir /path/to/working/MSC_Dataset \\
        --frames-per-shot 8

`--frames-per-shot` must match num_frames // num_shots as passed to
03_build_shot_windows.py / 07_extract_visual_features.py later (e.g. with
--num-frames 16 --num-shots 2, that's 8).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import av
import cv2
from tqdm import tqdm

from msc_pipeline_common import VIVIT_IMAGE_SIZE, resolve_dataset_dir, sample_indices


def load_shots(shots_csv: Path) -> list[str]:
    with open(shots_csv, newline="", encoding="utf-8") as f:
        return [row["filename"] for row in csv.DictReader(f)]


def extract_frames_for_shot(shot_path: Path, out_dir: Path, frames_per_shot: int, force: bool) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(out_dir.glob(f"{shot_path.stem}_*.png"))
    if existing and len(existing) == frames_per_shot and not force:
        return "skipped_existing"

    try:
        with av.open(str(shot_path)) as container:
            stream = container.streams.video[0]
            total_frames = stream.frames
            if not total_frames or total_frames <= 0:
                total_frames = sum(1 for _ in container.decode(stream))
                container.seek(0)
                stream = container.streams.video[0]

            if total_frames <= 0:
                return "no_frames"

            selected = set(sample_indices(list(range(total_frames)), frames_per_shot).keys())

            for i, frame in enumerate(container.decode(stream)):
                if i not in selected:
                    continue

                fname = f"{shot_path.stem}_{i:06d}.png"
                fpath = out_dir / fname
                if not fpath.exists() or force:
                    img = frame.to_ndarray(format="bgr24")
                    img = cv2.resize(img, VIVIT_IMAGE_SIZE)
                    cv2.imwrite(str(fpath), img)

                selected.discard(i)
                if not selected:
                    break

        return "saved"
    except Exception as exc:
        print(f"WARNING: error extracting frames from {shot_path}: {exc}")
        return "error"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="Working dataset directory (from 01_generate_shots.py). Frames go under frames_<N>/. "
                             "Default: <root-dir>/Datasets/MSC_Dataset (see --root-dir).")
    parser.add_argument("--root-dir", type=str, default=None,
                        help="Base directory to derive --dataset-dir from (as <root-dir>/Datasets/MSC_Dataset) when --dataset-dir is not given. "
                             "Falls back to the MSC_ROOT_DIR environment variable, then the current working directory. Ignored if --dataset-dir is given.")
    parser.add_argument("--shots-csv", type=Path, default=None,
                        help="Defaults to <dataset-dir>/metadata/shots.csv.")
    parser.add_argument("--frames-per-shot", type=int, required=True,
                        help="Number of key-frames to sample per shot (e.g. 8 for --num-frames 16 --num-shots 2).")
    parser.add_argument("--force", action="store_true", help="Re-extract even if a shot's frame directory already looks complete.")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    shots_csv = args.shots_csv or (dataset_dir / "metadata" / "shots.csv")
    frames_root = dataset_dir / f"frames_{args.frames_per_shot}"
    frames_root.mkdir(parents=True, exist_ok=True)

    shot_files = load_shots(shots_csv)
    print(f"{len(shot_files)} shots listed in {shots_csv}")

    stats = {"saved": 0, "skipped_existing": 0, "no_frames": 0, "error": 0}
    for filename in tqdm(shot_files, desc="Extracting key-frames"):
        shot_path = Path(filename)
        video_dir = frames_root / shot_path.parent.name
        outcome = extract_frames_for_shot(shot_path, video_dir, args.frames_per_shot, args.force)
        stats[outcome] = stats.get(outcome, 0) + 1

    print(
        f"Done | saved={stats['saved']} | skipped_existing={stats['skipped_existing']} | "
        f"no_frames={stats['no_frames']} | error={stats['error']}"
    )
    if stats["no_frames"]:
        print(
            f"{stats['no_frames']} shots produced no frames (typically shots too short to "
            f"sample {args.frames_per_shot} frames from -- ~0.8% of MSC shots historically). "
            f"These will be missing visual embeddings; see 08_filter_missing_visual.py."
        )


if __name__ == "__main__":
    main()
