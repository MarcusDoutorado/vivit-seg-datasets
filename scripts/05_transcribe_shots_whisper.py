#!/usr/bin/env python3
"""Transcribes every shot with OpenAI Whisper and writes a synthetic SRT
per movie, standing in for the official subtitles MSC doesn't have.

Ported from vivit-seg's src/preprocess/extract_text_from_shots.py. This is
where the worst hardcoded-path offender in the original pipeline lived: an
inline if/elif picking one of three fixed
`/home/marcus/Research/Datasets/{OVSD,BBC,MSC}_Dataset` paths by
--dataset-name. Replaced here with a plain --dataset-dir CLI arg.

For every shot in metadata/shots.csv, transcribes with Whisper (resumable --
skips shots whose .txt already exists), then per movie writes:
  - raw/subtitles/<msc_id>_whisper.srt   (synthetic SRT, empty shots omitted --
    06_extract_textual_features.py recovers them as empty when no SRT
    segment overlaps the shot)
  - raw/subtitles/<msc_id>.txt            (human-readable consolidated transcript)

Usage:
    python3 scripts/05_transcribe_shots_whisper.py \\
        --dataset-dir /path/to/working/MSC_Dataset \\
        --model base --language en

Requires the `openai-whisper` and `opencv-python` Python packages, and
`ffmpeg` on PATH (used internally by whisper).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import cv2
import pandas as pd
import whisper
from tqdm import tqdm

from msc_pipeline_common import resolve_dataset_dir


def get_video_fps(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video to determine FPS: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if not fps or fps <= 0:
        raise RuntimeError(f"Invalid FPS ({fps}) for video: {video_path}")
    return float(fps)


def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, milliseconds = divmod(total_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="Default: <root-dir>/Datasets/MSC_Dataset (see --root-dir).")
    parser.add_argument("--root-dir", type=str, default=None,
                        help="Base directory to derive --dataset-dir from (as <root-dir>/Datasets/MSC_Dataset) when --dataset-dir is not given. "
                             "Falls back to the MSC_ROOT_DIR environment variable, then the current working directory. Ignored if --dataset-dir is given.")
    parser.add_argument("--shots-csv", type=Path, default=None, help="Default: <dataset-dir>/metadata/shots.csv")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny/base/small/medium/large).")
    parser.add_argument("--language", default="en")
    parser.add_argument("--limit", type=int, default=None, help="Only transcribe the first N shots (debug).")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    shots_csv = args.shots_csv or (dataset_dir / "metadata" / "shots.csv")

    shots_root = dataset_dir / "raw" / "shots"
    output_root = dataset_dir / "raw" / "subtitles"
    output_root.mkdir(parents=True, exist_ok=True)

    shots_df = pd.read_csv(shots_csv)
    required_columns = {"begin", "end", "filename"}
    missing_columns = required_columns - set(shots_df.columns)
    if missing_columns:
        raise SystemExit(f"Missing columns in {shots_csv}: {missing_columns}")

    shot_metadata = {}
    for row in shots_df.itertuples(index=False):
        row_filename = Path(str(row.filename))
        shot_metadata[(row_filename.parent.name, row_filename.stem)] = {
            "begin": int(row.begin),
            "end": int(row.end),
            "filename": str(row_filename),
        }

    print(f"Loaded metadata for {len(shot_metadata)} shots from {shots_csv}")

    model = whisper.load_model(args.model)

    shot_files = sorted(shots_root.rglob("*.mp4"))
    if args.limit is not None:
        shot_files = shot_files[: args.limit]
    print(f"Transcribing {len(shot_files)} shots...")

    video_records = defaultdict(list)

    for shot in tqdm(shot_files, desc="Transcribing shots"):
        video_name, shot_name = shot.parent.name, shot.stem
        metadata = shot_metadata.get((video_name, shot_name))
        if metadata is None:
            print(f"WARNING: shot on disk but not in shots.csv, skipping: {shot}")
            continue

        shot_output_dir = output_root / video_name
        shot_output_dir.mkdir(parents=True, exist_ok=True)
        txt_file = shot_output_dir / f"{shot_name}.txt"

        try:
            if txt_file.exists():
                text = txt_file.read_text(encoding="utf-8").strip()
            else:
                result = model.transcribe(str(shot), language=args.language, fp16=False)
                text = result["text"].strip()
                txt_file.write_text(text, encoding="utf-8")

            fps = get_video_fps(str(shot))
            video_records[video_name].append({
                "shot_name": shot_name,
                "start": metadata["begin"] / fps,
                "end": metadata["end"] / fps,
                "text": text,
                "begin": metadata["begin"],
            })
        except Exception as exc:
            print(f"ERROR transcribing {shot}: {exc}")

    for video_name, records in video_records.items():
        records.sort(key=lambda r: r["begin"])

        consolidated_txt = output_root / f"{video_name}.txt"
        with consolidated_txt.open("w", encoding="utf-8") as f:
            for record in records:
                f.write("=" * 60 + "\n" + record["shot_name"] + "\n" + "=" * 60 + "\n")
                f.write(record["text"] if record["text"] else "[EMPTY]")
                f.write("\n\n")

        whisper_srt = output_root / f"{video_name}_whisper.srt"
        subtitle_index = 1
        with whisper_srt.open("w", encoding="utf-8") as f:
            for record in records:
                text = record["text"].strip()
                if not text:
                    continue  # empty shots omitted; recovered as empty downstream
                f.write(f"{subtitle_index}\n")
                f.write(f"{format_srt_timestamp(record['start'])} --> {format_srt_timestamp(record['end'])}\n")
                f.write(f"{text}\n\n")
                subtitle_index += 1

        print(f"{video_name}: {len(records)} shots transcribed -> {whisper_srt.name}")


if __name__ == "__main__":
    main()
