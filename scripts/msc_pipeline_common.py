"""Shared constants and small helpers used by the MSC reproduction scripts
(01_generate_shots.py through 08_filter_missing_visual.py).

This module has ZERO dependency on the vivit-seg model repository -- every
constant that vivit-seg defines in `setting.py` and every helper it defines
in `src/utils.py` / `src/preprocess/utils.py` that the ported scripts
actually need is reproduced here directly, so someone who has only cloned
vivit-seg-datasets can run the full pipeline standalone.

Not a framework: this is a handful of small, independent functions. Each
script in scripts/ imports only the pieces it needs.
"""
from __future__ import annotations

import ast
import os
import pickle
from collections import Counter
from pathlib import Path
from typing import Dict, List

# ----------------------------------------------------------------------
# Constants (mirrors the relevant subset of vivit-seg's setting.Setting)
# ----------------------------------------------------------------------

RANDOM_STATE = 42

LABEL_NOT_RELATED = 0
LABEL_RELATED = 1

# ViViT's expected square input resolution (google/vivit-b-16x2-kinetics400).
VIVIT_IMAGE_SIZE = (224, 224)
VIVIT_PRETRAINED_MODEL = "google/vivit-b-16x2-kinetics400"

# Pool size to draw per-row "gap" values from when building augmented
# (duplicated) not-related samples, so that augmented duplicates of the same
# underlying row sample different frame offsets from each other. Needs to
# comfortably exceed the largest number of augmented rows any single LOVO
# split will ever need (MSC's full 54-movie clean set needs ~90k).
DATA_AUGMENTATION_MAX_ARRAY = 200_000

MAX_AUDIO_LEN = 128
AUDIO_DIM_MFCC = 40
AUDIO_DIM_LOGMEL = 64

TEXTUAL_EMBEDDING_DIM = 384
VISUAL_EMBEDDING_DIM = 768


def get_audio_dim(feature_type: str) -> int:
    if feature_type == "mfcc":
        return AUDIO_DIM_MFCC
    elif feature_type == "logmel":
        return AUDIO_DIM_LOGMEL
    raise ValueError(f"Unknown audio feature type: {feature_type!r}")


# ----------------------------------------------------------------------
# Path / naming helpers
# ----------------------------------------------------------------------

def parse_path_names(path) -> tuple[str, str]:
    """('.../msc_0005/shot_0001.mp4') -> ('msc_0005', 'shot_0001')."""
    path = Path(path)
    return path.parent.name, path.stem


def natural_key(filename: str) -> int:
    """'shot_0012.mp4' -> 12. Falls back to 0 if no trailing number is found."""
    stem = Path(filename).stem
    try:
        return int(stem.split("_")[-1])
    except (IndexError, ValueError):
        return 0


def frames_dir_name(frames_per_shot: int) -> str:
    return f"frames_{frames_per_shot}"


def parse_literal(value):
    """Parses a CSV cell that stringifies a Python list/dict back to it."""
    if isinstance(value, (list, dict)):
        return value
    return ast.literal_eval(value)


# ----------------------------------------------------------------------
# Root-directory resolution
#
# MSC/shots_trust.csv's `filename` column implies a layout of
# <root_dir>/Datasets/MSC_Dataset/raw/shots/msc_XXXX/shot_NNNN.mp4 -- but
# where <root_dir> is depends entirely on where a given person keeps their
# Datasets folder. Every script accepts an explicit --dataset-dir override
# (pointing straight at .../MSC_Dataset) for full control, but when that's
# omitted, resolves a default from --root-dir / MSC_ROOT_DIR / cwd instead
# of forcing everyone to always spell out --dataset-dir.
# ----------------------------------------------------------------------

def get_root_dir(cli_value: str | None) -> Path:
    """Resolves the root directory in this precedence order:
    1. `cli_value` (from a script's --root-dir flag), if given.
    2. The MSC_ROOT_DIR environment variable, if set.
    3. The current working directory.
    """
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get("MSC_ROOT_DIR")
    if env_value:
        return Path(env_value)
    return Path.cwd()


def default_dataset_dir(root_dir: Path) -> Path:
    """<root_dir>/Datasets/MSC_Dataset -- the layout implied by
    shots_trust.csv's `filename` column (e.g. Datasets/MSC_Dataset/raw/shots/msc_0005/shot_0001.mp4)."""
    return root_dir / "Datasets" / "MSC_Dataset"


def resolve_dataset_dir(dataset_dir_cli: str | None, root_dir_cli: str | None) -> Path:
    """What every script's main() calls right after argparse: honors an
    explicit --dataset-dir override untouched, else derives the dataset
    directory from --root-dir / MSC_ROOT_DIR / cwd (see get_root_dir)."""
    if dataset_dir_cli:
        return Path(dataset_dir_cli).expanduser().resolve()
    return default_dataset_dir(get_root_dir(root_dir_cli)).expanduser().resolve()


# ----------------------------------------------------------------------
# Frame-index sampling (used both when extracting PNG key-frames per shot,
# and when recording which of those frame indices a given dataset row uses)
# ----------------------------------------------------------------------

def sample_indices(frame_indices: List[int], k: int) -> Dict[int, int]:
    """Uniformly samples k indices out of frame_indices (with repeats if
    frame_indices has fewer than k elements). Returns {frame_idx: count}."""
    if len(frame_indices) == 0:
        return {}

    if len(frame_indices) >= k:
        idxs = _linspace_int(0, len(frame_indices) - 1, k)
        selected = [frame_indices[i] for i in idxs]
    else:
        repeats = -(-k // len(frame_indices))  # ceil division
        selected = (frame_indices * repeats)[:k]

    counts = Counter(selected)
    return {int(idx): int(count) for idx, count in counts.items()}


def sample_indices_gap(frame_indices: List[int], gap: int, k: int) -> Dict[int, int]:
    """Samples k indices out of frame_indices by walking with a fixed step
    ('gap'), wrapping around. Used to give each augmented (duplicated) row a
    distinct-looking sampling of the same underlying shot."""
    if len(frame_indices) == 0:
        return {}

    if gap <= 0:
        gap = 1

    selected = []
    idx = 0
    for _ in range(k):
        selected.append(frame_indices[idx])
        idx = (idx + gap) % len(frame_indices)

    counts = Counter(selected)
    return {int(idx): int(count) for idx, count in counts.items()}


def _linspace_int(start: int, stop: int, num: int) -> List[int]:
    """Integer-rounded evenly spaced sample, equivalent to
    numpy.linspace(start, stop, num, dtype=int) but without a numpy
    dependency for callers that don't otherwise need it."""
    if num == 1:
        return [start]
    step = (stop - start) / (num - 1)
    return [int(round(start + step * i)) for i in range(num)]


# ----------------------------------------------------------------------
# Feature metadata + saving (mirrors src/preprocess/utils.py)
# ----------------------------------------------------------------------

def build_feature_metadata(
    modality,
    extractor,
    embedding,
    video,
    shot,
    frames_per_shot=None,
    num_shots=None,
    transition_pos=None,
    image_size=None,
    experiment_id=None,
):
    return {
        "video": video,
        "shot": shot,
        "modality": modality,
        "extractor": extractor,
        "embedding_dim": int(embedding.shape[-1]),
        "embedding_shape": list(embedding.shape),
        "temporal_embedding": len(embedding.shape) == 2,
        "dtype": str(embedding.dtype),
        "experiment": {
            "id": experiment_id,
            "frames_per_shot": frames_per_shot,
            "num_shots": num_shots,
            "total_frames": (
                frames_per_shot * num_shots
                if frames_per_shot is not None and num_shots is not None
                else None
            ),
            "transition_pos": transition_pos,
            "image_size": image_size,
        },
        "version": 1,
    }


def save_pkl(path, embedding, metadata):
    obj = {"embedding": embedding, "metadata": metadata}
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


def save_feature(output_file, embedding, metadata):
    save_pkl(output_file, embedding, metadata)
