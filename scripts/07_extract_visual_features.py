#!/usr/bin/env python3
"""Extracts ViViT visual embeddings per shot, from the PNG key-frames
produced by 02_extract_key_frames.py.

Ported from vivit-seg's src/preprocess/extract_visual_features.py +
feature_extractors/visual.py, "current" per-shot embedding mode only. Per
scope agreed for this port, deliberately dropped:
  - the "legacy" embedding mode (sample-level ViViT classifier-input caching
    for the full multi-shot window, keyed by exact shot paths + frame
    indices) and its visual_embedding_cache.py companion;
  - four visual-embedding strategy names vivit-seg lists but never actually
    implements (attention_pool, cls_residual, multi_layer, spatial_temporal --
    selecting them in the original code raises ValueError). Only strategies
    with a real implementation are exposed via --visual-embedding (see
    feature_extractors.py's VISUAL_EMBEDDING_STRATEGIES).

`temporal_mean` is the default and the strategy actually used for MSC's
reported results.

Usage (matches vivit-seg's setup_msc_dataset_gpu.sh for MSC):
    python3 scripts/07_extract_visual_features.py \\
        --dataset-dir /path/to/working/MSC_Dataset \\
        --num-frames 16 --num-shots 2 --visual-embedding temporal_mean

Requires the `torch`, `torchvision`, `transformers`, `opencv-python` Python
packages, and downloads google/vivit-b-16x2-kinetics400 from HuggingFace on
first run. GPU strongly recommended but not required.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

from feature_extractors import (
    DEFAULT_VISUAL_EMBEDDING_STRATEGY,
    VISUAL_EMBEDDING_STRATEGIES,
    ViViTExtractor,
)
from msc_pipeline_common import VIVIT_PRETRAINED_MODEL, build_feature_metadata, parse_path_names, resolve_dataset_dir, save_feature


def load_shot_frames(frames_dir: Path, shot_name: str, expected_num_frames: int) -> list:
    frame_files = sorted(frames_dir.glob(f"{shot_name}_*.png"))
    if not frame_files:
        raise FileNotFoundError(f"No frames found for shot '{shot_name}' in '{frames_dir}'.")

    frames = []
    for file in frame_files:
        img = cv2.imread(str(file), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Could not read frame: {file}")
        frames.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))  # ViViT processor expects RGB

    current = len(frames)
    if current == expected_num_frames:
        return frames

    if current > expected_num_frames:
        indices = np.linspace(0, current - 1, expected_num_frames, dtype=int)
        frames = [frames[i] for i in indices]
    else:
        last = frames[-1]
        frames.extend([last.copy() for _ in range(expected_num_frames - current)])

    return frames


def extract_shot(dataset_dir: Path, extractor, shot, feature_dir_name: str, experiment_id, frames_per_shot, num_shots, transition_pos, overwrite: bool) -> str:
    video_name, shot_name = parse_path_names(shot.filename)
    frames_dir = dataset_dir / f"frames_{frames_per_shot}" / video_name

    video_out_dir = dataset_dir / feature_dir_name / video_name
    video_out_dir.mkdir(parents=True, exist_ok=True)
    output_file = video_out_dir / f"{shot_name}.pkl"

    if output_file.exists() and not overwrite:
        return "skipped_existing"

    try:
        frames = load_shot_frames(frames_dir, shot_name, expected_num_frames=frames_per_shot)
    except FileNotFoundError:
        # Shots too short to sample frames_per_shot frames from (~0.8% of MSC
        # shots historically, concentrated in very quick cuts). Skip and
        # count rather than aborting the whole run -- see 08_filter_missing_visual.py.
        return "missing_frames"

    embedding = extractor.extract(frames)
    metadata = build_feature_metadata(
        modality="visual", extractor=VIVIT_PRETRAINED_MODEL, embedding=embedding,
        video=video_name, shot=shot_name, frames_per_shot=frames_per_shot,
        num_shots=num_shots, transition_pos=transition_pos,
        image_size=(224, 224), experiment_id=experiment_id,
    )
    save_feature(output_file, embedding, metadata)
    return "saved"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="Default: <root-dir>/Datasets/MSC_Dataset (see --root-dir).")
    parser.add_argument("--root-dir", type=str, default=None,
                        help="Base directory to derive --dataset-dir from (as <root-dir>/Datasets/MSC_Dataset) when --dataset-dir is not given. "
                             "Falls back to the MSC_ROOT_DIR environment variable, then the current working directory. Ignored if --dataset-dir is given.")
    parser.add_argument("--shots-csv", type=Path, default=None, help="Default: <dataset-dir>/metadata/shots.csv")
    parser.add_argument("--num-frames", type=int, default=16, help="Total frames per window (must match 02_extract_key_frames.py / 03_build_shot_windows.py).")
    parser.add_argument("--num-shots", type=int, default=2)
    parser.add_argument("--transition-pos", type=int, default=2)
    parser.add_argument("--visual-embedding", choices=VISUAL_EMBEDDING_STRATEGIES, default=DEFAULT_VISUAL_EMBEDDING_STRATEGY)
    parser.add_argument("--model-name", default=VIVIT_PRETRAINED_MODEL)
    parser.add_argument("--device", default=None, help="Default: cuda if available, else cpu.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N shots (debug).")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate existing embedding files.")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    shots_csv = args.shots_csv or (dataset_dir / "metadata" / "shots.csv")
    shots_df = pd.read_csv(shots_csv)
    if args.limit is not None:
        shots_df = shots_df.iloc[: args.limit]

    frames_per_shot = args.num_frames // args.num_shots
    feature_dir_name = f"embeddings/visual/vivit_{args.visual_embedding}"

    print(f"Loading ViViT ({args.model_name}), strategy={args.visual_embedding}, frames_per_shot={frames_per_shot} ...")
    extractor = ViViTExtractor(
        frames_per_shot=frames_per_shot,
        model_name=args.model_name,
        device=args.device,
        strategy=args.visual_embedding,
    )

    stats = {"saved": 0, "skipped_existing": 0, "missing_frames": 0}
    for shot in tqdm(shots_df.itertuples(index=False), total=len(shots_df), desc="Visual embeddings"):
        outcome = extract_shot(
            dataset_dir, extractor, shot, feature_dir_name,
            experiment_id=f"vivit_{args.num_frames}f",
            frames_per_shot=frames_per_shot, num_shots=args.num_shots,
            transition_pos=args.transition_pos, overwrite=args.overwrite,
        )
        stats[outcome] = stats.get(outcome, 0) + 1

    print(f"Done | saved={stats['saved']} | skipped_existing={stats['skipped_existing']} | missing_frames={stats['missing_frames']}")
    if stats["missing_frames"]:
        print(
            f"{stats['missing_frames']} shots have no visual embedding (too short to sample "
            f"{frames_per_shot} frames from). Run 08_filter_missing_visual.py before training "
            f"on the dataset CSVs from 03_build_shot_windows.py."
        )


if __name__ == "__main__":
    main()
