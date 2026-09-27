#!/usr/bin/env python3
"""Cuts raw MSC movie files into per-shot .mp4 clips using the verified
shot/scene groundtruth (MSC/shots_trust.csv, MSC/scenes_trust.csv), and
writes the metadata/shots.csv + metadata/scenes.csv that every later script
in this pipeline reads.

Adapted, near-verbatim, from vivit-seg's experiment_manager/msc_generate_shots.py
(the mechanical "cut the raw video at this frame range" part is annotation-driven,
not pipeline-derived, so there's nothing to improve on there) -- generalized to:
  - take the dataset directory as a CLI arg instead of a hardcoded path;
  - locate each raw movie by the filename documented in MSC/msc_movies.csv and
    docs/download_guide.md (`fileName`, with the alternate filename in the
    unlabeled trailing column tried as a fallback), instead of requiring the
    file be pre-renamed to `msc_XXXX.ext`;
  - after cutting, recompute each shot's real frame count directly from the
    cut clip (via PyAV) rather than trusting the annotation's frame count,
    exactly like vivit-seg's src/utils.py:load_gt_shots does -- this is what
    ends up in metadata/shots.csv's `frames` column.

Directory layout produced under --dataset-dir:
    raw/shots/msc_XXXX/shot_NNNN.mp4   (cut per-shot clips)
    metadata/shots.csv                  (begin,end,frames,filename)
    metadata/scenes.csv                 (begin,end,scene,video)

Usage:
    python3 scripts/01_generate_shots.py \\
        --videos-dir /path/to/your/msc/videos \\
        --dataset-dir /path/to/working/MSC_Dataset

    # Only a couple of movies (e.g. for a quick smoke test):
    python3 scripts/01_generate_shots.py \\
        --videos-dir /path/to/your/msc/videos \\
        --dataset-dir /path/to/working/MSC_Dataset \\
        --movies msc_0005

Requires the `ffmpeg`/`ffprobe` binaries on PATH, and the `av` (PyAV) and
`tqdm` Python packages.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import av
from tqdm import tqdm

from msc_pipeline_common import resolve_dataset_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
MSC_DIR = REPO_ROOT / "MSC"


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_movies_csv(path: Path) -> dict[str, list[str]]:
    """msc_id (lowercase, e.g. 'msc_0005') -> candidate filenames to look for
    in --videos-dir, in priority order (primary fileName, then the alternate
    filename some rows carry in the unlabeled trailing column, if any)."""
    candidates: dict[str, list[str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            d = dict(zip(header, row))
            msc_id = d["msc_id"].lower()
            names = [d["fileName"]] if d.get("fileName") else []
            alt = d.get("")
            if alt:
                names.append(alt)
            candidates[msc_id] = names
    return candidates


def get_fps(video_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    rate = json.loads(result.stdout)["streams"][0]["r_frame_rate"]
    num, den = map(int, rate.split("/"))
    return num / den


def count_frames(video_path: Path) -> int:
    """Real frame count of a cut shot clip, via PyAV (matches vivit-seg's
    src/utils.py:get_num_frames)."""
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        frames = stream.frames
        if frames and frames > 0:
            return frames
        # Container didn't report a frame count in its header (rare, some
        # re-encoded clips) -- fall back to decoding and counting directly.
        return sum(1 for _ in container.decode(stream))


def find_movie_file(videos_dir: Path, candidate_names: list[str]) -> Path | None:
    for name in candidate_names:
        candidate = videos_dir / name
        if candidate.is_file():
            return candidate
    return None


def cut_shots_for_movie(msc_id: str, video_path: Path, shots: list[tuple[int, int]], shots_root: Path) -> Path:
    fps = get_fps(video_path)
    output_dir = shots_root / msc_id
    output_dir.mkdir(parents=True, exist_ok=True)

    for idx, (start_frame, end_frame) in enumerate(shots, 1):
        if end_frame < start_frame:
            end_frame = start_frame

        output_path = output_dir / f"shot_{idx:04d}.mp4"
        if output_path.exists():
            continue

        start_time = f"{start_frame / fps:.6f}"
        end_time = f"{(end_frame + 1) / fps:.6f}"

        cmd = [
            "ffmpeg", "-loglevel", "error", "-y", "-threads", "0",
            "-ss", start_time, "-to", end_time,
            "-i", str(video_path),
            "-c", "copy",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not output_path.exists():
            # -c copy can fail when the cut point doesn't land on a keyframe;
            # fall back to re-encoding.
            cmd_reencode = [
                "ffmpeg", "-loglevel", "error", "-y", "-threads", "0",
                "-ss", start_time, "-to", end_time,
                "-i", str(video_path),
                str(output_path),
            ]
            subprocess.run(cmd_reencode, capture_output=True, text=True, check=True)

    return output_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--videos-dir", type=Path, required=True,
                        help="Folder containing your sourced MSC movie files, named per MSC/msc_movies.csv's fileName column (see docs/download_guide.md).")
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="Working directory for the reproduced dataset (created if missing). Shot clips go under raw/shots/, metadata CSVs under metadata/. "
                             "Default: <root-dir>/Datasets/MSC_Dataset (see --root-dir).")
    parser.add_argument("--root-dir", type=str, default=None,
                        help="Base directory to derive --dataset-dir from (as <root-dir>/Datasets/MSC_Dataset) when --dataset-dir is not given. "
                             "Falls back to the MSC_ROOT_DIR environment variable, then the current working directory. Ignored if --dataset-dir is given.")
    parser.add_argument("--shots-csv", type=Path, default=MSC_DIR / "shots_trust.csv",
                        help="Verified shot groundtruth (default: MSC/shots_trust.csv).")
    parser.add_argument("--scenes-csv", type=Path, default=MSC_DIR / "scenes_trust.csv",
                        help="Verified scene groundtruth (default: MSC/scenes_trust.csv).")
    parser.add_argument("--movies-csv", type=Path, default=MSC_DIR / "msc_movies.csv",
                        help="Movie id -> filename lookup (default: MSC/msc_movies.csv).")
    parser.add_argument("--movies", nargs="*", default=None,
                        help="Only process these msc_ids (e.g. msc_0005 msc_0032). Default: all movies present in --shots-csv.")
    args = parser.parse_args()

    dataset_dir = resolve_dataset_dir(args.dataset_dir, args.root_dir)
    print(f"Using dataset directory: {dataset_dir}")
    shots_root = dataset_dir / "raw" / "shots"
    metadata_dir = dataset_dir / "metadata"
    shots_root.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    shots_rows = load_csv(args.shots_csv)
    scenes_rows = load_csv(args.scenes_csv)
    movie_candidates = load_movies_csv(args.movies_csv)

    # Group verified shot boundaries by movie, preserving on-disk shot order.
    shots_by_movie: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in shots_rows:
        msc_id = Path(row["filename"]).parent.name
        shots_by_movie[msc_id].append((int(row["begin"]), int(row["end"])))

    wanted = set(args.movies) if args.movies else set(shots_by_movie.keys())

    print(f"Movies in shots-csv: {len(shots_by_movie)} | selected for this run: {len(wanted)}")

    processed = []
    missing_movie_file = []

    for msc_id in sorted(shots_by_movie):
        if msc_id not in wanted:
            continue

        candidates = movie_candidates.get(msc_id, [])
        video_path = find_movie_file(args.videos_dir, candidates)
        if video_path is None:
            missing_movie_file.append((msc_id, candidates))
            continue

        cut_shots_for_movie(msc_id, video_path, shots_by_movie[msc_id], shots_root)
        processed.append(msc_id)

    print(f"Cut shots for {len(processed)}/{len(wanted)} requested movies.")
    if missing_movie_file:
        print(f"Movie file not found in --videos-dir for {len(missing_movie_file)} movies:")
        for msc_id, candidates in missing_movie_file:
            print(f"  {msc_id}: tried {candidates or '(no filename on record)'}")

    # ------------------------------------------------------------------
    # Build metadata/shots.csv: recompute the real per-shot frame count
    # from the cut clip (not trusted from the annotation), same as
    # vivit-seg's src/utils.py:load_gt_shots.
    # ------------------------------------------------------------------
    shots_out_rows = []
    for msc_id in processed:
        video_dir = shots_root / msc_id
        shot_files = sorted(video_dir.glob("shot_*.mp4"))
        boundaries = shots_by_movie[msc_id]
        if len(shot_files) != len(boundaries):
            print(
                f"WARNING: {msc_id}: {len(shot_files)} shot files on disk but "
                f"{len(boundaries)} boundaries in shots-csv -- using min(len) pairs."
            )
        for (begin, end), shot_path in zip(boundaries, shot_files):
            try:
                frames = count_frames(shot_path)
            except Exception as exc:
                print(f"WARNING: could not count frames for {shot_path}: {exc} -- skipping this shot.")
                continue
            shots_out_rows.append({
                "begin": begin,
                "end": end,
                "frames": frames,
                "filename": str(shot_path),
            })

    shots_out_rows.sort(key=lambda r: r["filename"])

    shots_csv_out = metadata_dir / "shots.csv"
    with open(shots_csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["begin", "end", "frames", "filename"])
        writer.writeheader()
        writer.writerows(shots_out_rows)
    print(f"Wrote {len(shots_out_rows)} shot rows to {shots_csv_out}")

    # ------------------------------------------------------------------
    # Build metadata/scenes.csv: verified scene groundtruth, filtered down
    # to the movies actually processed this run (video ids match the
    # numeric suffix of msc_XXXX, e.g. msc_0005 -> 5).
    # ------------------------------------------------------------------
    processed_video_ids = {str(int(msc_id.split("_")[-1])) for msc_id in processed}
    scenes_out_rows = [row for row in scenes_rows if row["video"] in processed_video_ids]
    scenes_out_rows.sort(key=lambda r: (int(r["video"]), int(r["scene"])))

    scenes_csv_out = metadata_dir / "scenes.csv"
    with open(scenes_csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["begin", "end", "scene", "video"])
        writer.writeheader()
        writer.writerows(scenes_out_rows)
    print(f"Wrote {len(scenes_out_rows)} scene rows to {scenes_csv_out}")


if __name__ == "__main__":
    main()
