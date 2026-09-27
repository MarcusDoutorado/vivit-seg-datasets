#!/usr/bin/env python3
"""Builds sentence-transformers embeddings per shot from the Whisper SRT
produced by 05_transcribe_shots_whisper.py.

Ported from vivit-seg's src/preprocess/extract_textual_features.py. For each
shot, finds the SRT segments whose timespan overlaps the shot's [begin, end]
frame range, concatenates their text, and encodes it with
sentence-transformers/all-MiniLM-L6-v2 (384-dim, L2-normalized).

Empty-shot imputation: a shot with no overlapping SRT text (common -- pure
visual beats, background shots) gets its *embedding* computed from the next
non-empty shot's text instead of an empty string, on the theory that a
transcript gap usually just means the boundary between subtitle timing and
this shot's cut, not that the shot has no attributable dialogue. The
*original* per-shot text file always records what was actually found
(possibly nothing), independent of this imputation -- only the embedding
uses the substitute text. Disable with --no-impute-empty-text.

Writes:
  - textual_text/<msc_id>/<shot>.txt + textual_text/<msc_id>.txt (original text, pre-imputation)
  - embeddings/textual/sentence_transformer/<msc_id>/<shot>.pkl   (embedding, post-imputation)

Usage:
    python3 scripts/06_extract_textual_features.py --dataset-dir /path/to/working/MSC_Dataset

Requires the `sentence-transformers` and `opencv-python` Python packages.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import cv2
import pandas as pd

from feature_extractors import TextualExtractor
from msc_pipeline_common import TEXTUAL_EMBEDDING_DIM, build_feature_metadata, resolve_dataset_dir, save_feature


def get_video_fps(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video to determine FPS: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if not fps or fps <= 0:
        raise RuntimeError(f"Invalid FPS ({fps}) for video: {video_path}")
    return float(fps)


def parse_srt_time(value: str) -> float:
    hh, mm, ss_ms = value.replace(",", ".").split(":")
    ss, ms = ss_ms.split(".")
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def read_srt_segments(srt_path: Path) -> list[dict]:
    if not srt_path.exists():
        return []

    content = srt_path.read_text(encoding="utf-8", errors="ignore")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", content) if b.strip()]

    segments = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2 or " --> " not in lines[1]:
            continue
        start_str, end_str = lines[1].split(" --> ", maxsplit=1)
        try:
            start, end = parse_srt_time(start_str), parse_srt_time(end_str)
        except ValueError:
            continue
        segments.append({"start": start, "end": end, "text": " ".join(lines[2:])})
    return segments


def extract_shot_text(shot, segments: list[dict], fps: float) -> str:
    shot_start = float(shot.begin) / fps
    shot_end = float(shot.end) / fps
    snippets = [
        seg["text"] for seg in segments
        if seg["start"] < shot_end and seg["end"] > shot_start
    ]
    return " ".join(snippets).strip()


def impute_empty_texts(shot_texts: dict[str, str]) -> dict[str, str]:
    """Empty shots get the text of the next non-empty shot, for embedding
    purposes only. Trailing empty shots with no subsequent text stay empty."""
    items = list(shot_texts.items())
    result = dict(shot_texts)
    for i, (shot_name, text) in enumerate(items):
        if text.strip():
            continue
        for next_shot_name, next_text in items[i + 1:]:
            if next_text.strip():
                result[shot_name] = next_text
                break
    return result


def save_shot_text(output_dir: Path, shot_name: str, text: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{shot_name}.txt").write_text(text or "[EMPTY]", encoding="utf-8")


def save_video_text(output_dir: Path, video_name: str, shot_texts: dict[str, str]):
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / f"{video_name}.txt").open("w", encoding="utf-8") as f:
        for shot_name, text in shot_texts.items():
            f.write("=" * 60 + "\n" + shot_name + "\n" + "=" * 60 + "\n")
            f.write(text if text else "[EMPTY]")
            f.write("\n\n")


def process_video(dataset_dir: Path, video_name: str, video_shots, embeddings_root: Path, extractor, impute_empty: bool):
    srt_path = dataset_dir / "raw" / "subtitles" / f"{video_name}_whisper.srt"
    if not srt_path.exists():
        print(f"WARNING: no SRT found for {video_name} ({srt_path}), skipping.")
        return

    segments = read_srt_segments(srt_path)
    if not segments:
        print(f"WARNING: no SRT segments parsed for {video_name}, skipping.")
        return

    shot_texts = {}
    for shot in video_shots:
        shot_name = Path(shot.filename).stem
        fps = get_video_fps(shot.filename)
        shot_texts[shot_name] = extract_shot_text(shot, segments, fps)

    textual_text_dir = dataset_dir / "textual_text"
    for shot_name, text in shot_texts.items():
        save_shot_text(textual_text_dir / video_name, shot_name, text)
    save_video_text(textual_text_dir, video_name, shot_texts)

    embedding_texts = impute_empty_texts(shot_texts) if impute_empty else shot_texts

    video_out_dir = embeddings_root / video_name
    video_out_dir.mkdir(parents=True, exist_ok=True)

    for shot in video_shots:
        shot_name = Path(shot.filename).stem
        output_file = video_out_dir / f"{shot_name}.pkl"
        if output_file.exists():
            continue

        embedding = extractor.extract(embedding_texts[shot_name])
        metadata = build_feature_metadata(
            modality="textual", extractor="textual", embedding=embedding,
            video=video_name, shot=shot_name, experiment_id="textual",
            # Textual embeddings don't depend on the shot-window config (text
            # is per-shot, not per-window) -- these two fields are recorded
            # purely for metadata parity with the audio/visual embeddings'
            # experiment block, matching vivit-seg's own (hardcoded) values.
            num_shots=2, transition_pos=2,
        )
        save_feature(output_file, embedding, metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="Default: <root-dir>/Datasets/MSC_Dataset (see --root-dir).")
    parser.add_argument("--root-dir", type=str, default=None,
                        help="Base directory to derive --dataset-dir from (as <root-dir>/Datasets/MSC_Dataset) when --dataset-dir is not given. "
                             "Falls back to the MSC_ROOT_DIR environment variable, then the current working directory. Ignored if --dataset-dir is given.")
    parser.add_argument("--shots-csv", type=Path, default=None, help="Default: <dataset-dir>/metadata/shots.csv")
    parser.add_argument("--model-name", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--no-impute-empty-text", action="store_true",
                        help="Disable next-shot imputation for embeddings of shots with no transcribed text.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N movies (debug).")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    shots_csv = args.shots_csv or (dataset_dir / "metadata" / "shots.csv")
    shots_df = pd.read_csv(shots_csv)

    embeddings_root = dataset_dir / "embeddings" / "textual" / "sentence_transformer"
    embeddings_root.mkdir(parents=True, exist_ok=True)

    extractor = TextualExtractor(model_name=args.model_name, embedding_dim=TEXTUAL_EMBEDDING_DIM)

    grouped_shots: dict[str, list] = {}
    for shot in shots_df.itertuples(index=False):
        video_name = Path(shot.filename).parent.name
        grouped_shots.setdefault(video_name, []).append(shot)
    for video_name in grouped_shots:
        grouped_shots[video_name].sort(key=lambda s: (int(s.begin), int(s.end)))

    processed = 0
    for video_name, video_shots in grouped_shots.items():
        if args.limit is not None and processed >= args.limit:
            break
        print(f"Processing textual features for {video_name} ({len(video_shots)} shots)")
        process_video(dataset_dir, video_name, video_shots, embeddings_root, extractor, not args.no_impute_empty_text)
        processed += 1


if __name__ == "__main__":
    main()
