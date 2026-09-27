#!/usr/bin/env python3
"""Extracts audio features (MFCC or LogMel) per shot, then normalizes them
into fixed-length embeddings.

Ported from vivit-seg's src/preprocess/extract_audio_features.py +
feature_extractors/audio.py. Two independent steps, matching the original's
--generate-features / --generate-embeddings flags:

  1. --generate-features: extracts each shot's audio via ffmpeg (16kHz mono
     PCM), computes raw MFCC (40-dim) or LogMel (64-dim) via librosa,
     z-score normalizes, and saves as features/aural/<feature_type>/<msc_id>/<shot>.npy.
  2. --generate-embeddings: loads those .npy files, transposes to (time, dim),
     re-normalizes, and pads/truncates to --max-audio-len (128) frames, saving
     as embeddings/aural/<feature_type>/<msc_id>/<shot>.pkl.

Simplified vs. the original: dropped the "legacy audio_features/<video>/<shot>_<type>.npy"
layout fallback (BBC/OVSD only, irrelevant for this from-scratch MSC pipeline).

Usage:
    python3 scripts/04_extract_audio_features.py \\
        --dataset-dir /path/to/working/MSC_Dataset \\
        --feature-type mfcc --generate-features --generate-embeddings

Requires `ffmpeg` on PATH, and the `librosa` Python package.
"""
from __future__ import annotations

import argparse
import subprocess
from multiprocessing import Pool, cpu_count
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
from tqdm import tqdm

from feature_extractors import AudioExtractor
from msc_pipeline_common import build_feature_metadata, get_audio_dim, parse_path_names, resolve_dataset_dir, save_feature


def extract_audio(video_path: Path, audio_path: Path):
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(audio_path), "-y",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def compute_feature(y, sr, feature_type: str) -> np.ndarray:
    n_fft = 2048
    hop_length = 512

    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))

    if feature_type == "mfcc":
        feat = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40, n_fft=n_fft, hop_length=hop_length)
    elif feature_type == "logmel":
        mel_spec = librosa.feature.melspectrogram(
            y=y, sr=sr, n_fft=n_fft, hop_length=hop_length, n_mels=64, power=2.0
        )
        feat = librosa.power_to_db(mel_spec, ref=np.max)
    else:
        raise ValueError(f"Invalid feature type: {feature_type}")

    feat = (feat - feat.mean()) / (feat.std() + 1e-6)
    return feat


def process_shot(video_path: str, feature_root: Path, feature_type: str) -> str:
    video_path = Path(video_path)
    if not video_path.exists():
        return "missing_video"

    video_name, shot_name = parse_path_names(video_path)
    out_dir = feature_root / feature_type / video_name
    out_dir.mkdir(parents=True, exist_ok=True)
    feature_file = out_dir / f"{shot_name}.npy"

    if feature_file.exists():
        try:
            feat = np.load(feature_file)
            audio_dim = get_audio_dim(feature_type)
            if feat.ndim == 2 and feat.shape[1] > 1 and (feat.shape[0] == audio_dim or feat.shape[1] == audio_dim):
                return "skipped_existing"
        except Exception:
            pass  # fall through and reprocess

    temp_audio = out_dir / f"{video_path.stem}.wav"
    extract_audio(video_path, temp_audio)

    try:
        y, sr = librosa.load(temp_audio, sr=16000)
        if len(y) < sr * 0.1:
            return "too_short_audio"
        feat = compute_feature(y, sr, feature_type)
        np.save(feature_file, feat)
        return "saved"
    except Exception as exc:
        print(f"WARNING: feature extraction error for {video_path}: {exc}")
        return "feature_error"
    finally:
        if temp_audio.exists():
            temp_audio.unlink()


def _feature_worker(task):
    video_path, feature_root, feature_type = task
    return process_shot(video_path, feature_root, feature_type)


def extract_shot_embedding(dataset_dir: Path, extractor: AudioExtractor, shot, feature_root: Path, embeddings_root: Path, feature_type: str, experiment_id: str) -> str:
    video_name, shot_name = parse_path_names(shot.filename)
    input_file = feature_root / feature_type / video_name / f"{shot_name}.npy"

    if not input_file.exists():
        return "missing_feature"

    video_out_dir = embeddings_root / feature_type / video_name
    video_out_dir.mkdir(parents=True, exist_ok=True)
    output_file = video_out_dir / f"{shot_name}.pkl"
    if output_file.exists():
        return "skipped_existing"

    try:
        feature = np.load(input_file)
        embedding = extractor.extract(feature)
    except Exception as exc:
        print(f"WARNING: embedding extraction error for {input_file}: {exc}")
        return "embedding_error"

    metadata = build_feature_metadata(
        modality="audio", extractor=feature_type, embedding=embedding,
        video=video_name, shot=shot_name, experiment_id=experiment_id,
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
    parser.add_argument("--feature-type", choices=["mfcc", "logmel"], default="mfcc")
    parser.add_argument("--generate-features", action="store_true", help="Step 1: raw MFCC/LogMel .npy per shot.")
    parser.add_argument("--generate-embeddings", action="store_true", help="Step 2: normalized, fixed-length .pkl embeddings per shot.")
    parser.add_argument("--max-audio-len", type=int, default=128, help="Fixed sequence length embeddings are padded/truncated to.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N shots (debug).")
    parser.add_argument("--workers", type=int, default=None, help="Parallel workers for --generate-features (default: cpu_count()).")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    shots_csv = args.shots_csv or (dataset_dir / "metadata" / "shots.csv")
    shots_df = pd.read_csv(shots_csv)
    if args.limit is not None:
        shots_df = shots_df.iloc[: args.limit]

    feature_root = dataset_dir / "features" / "aural"
    embeddings_root = dataset_dir / "embeddings" / "aural"

    if args.generate_features:
        print(f"Generating {args.feature_type.upper()} features for {len(shots_df)} shots...")
        tasks = [(row["filename"], feature_root, args.feature_type) for row in shots_df.to_dict("records")]

        stats = {"saved": 0, "skipped_existing": 0, "too_short_audio": 0, "missing_video": 0, "feature_error": 0}
        with Pool(args.workers or cpu_count()) as pool:
            for status in tqdm(pool.imap(_feature_worker, tasks), total=len(tasks), desc="Audio features"):
                stats[status] = stats.get(status, 0) + 1
        print(f"Feature generation summary: {stats}")

    if args.generate_embeddings:
        extractor = AudioExtractor(
            feature_type=args.feature_type,
            audio_dim=get_audio_dim(args.feature_type),
            max_audio_len=args.max_audio_len,
        )
        stats = {"saved": 0, "skipped_existing": 0, "missing_feature": 0, "embedding_error": 0}
        for shot in tqdm(shots_df.itertuples(index=False), total=len(shots_df), desc="Audio embeddings"):
            status = extract_shot_embedding(
                dataset_dir, extractor, shot, feature_root, embeddings_root,
                args.feature_type, experiment_id=f"{args.feature_type}_embeddings",
            )
            stats[status] = stats.get(status, 0) + 1
        print(f"Embedding generation summary: {stats}")


if __name__ == "__main__":
    main()
