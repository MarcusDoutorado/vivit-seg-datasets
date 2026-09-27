#!/usr/bin/env python3
"""Verifies that a locally-sourced copy of the 54 MSC movies matches what
MSC/shots_trust.csv and MSC/scenes_trust.csv were built against.

For each movie in MSC/msc_manifest.csv, checks (in order, cheapest first):
  1. SHA-256 checksum against MSC/msc_checksums.csv -- exact match means
     byte-identical to our reference copy: PASS immediately.
  2. If the checksum differs (or wasn't recorded), falls back to comparing
     ffprobe-measured frame count, frame rate (fps), and duration against
     MSC/msc_ffprobe_verification.csv (measured on our own reference copy) --
     within --frame-tolerance frames: PASS ("different encode, same content").
     Beyond tolerance: FAIL.
  3. File missing from --videos-dir: FAIL ("missing").

A checksum PASS is the strongest guarantee (byte-identical). An ffprobe PASS
means frame count/rate/duration line up closely, which is what actually
matters for shots_trust.csv/scenes_trust.csv's frame-indexed boundaries to
apply correctly -- but does not rule out an internal re-cut you'd only catch
by eye, so also spot-check MSC/verification_frames/ for anything you plan to
rely on for published results.

Requires the `ffprobe` binary (part of ffmpeg) on PATH for step 2.

Usage:
    python3 scripts/verify_msc_download.py --videos-dir /path/to/your/msc/videos
    python3 scripts/verify_msc_download.py --videos-dir /path/to/videos --report-out report.csv
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MSC = ROOT / "MSC"

DEFAULT_FRAME_TOLERANCE = 5
DEFAULT_FPS_TOLERANCE = 0.01


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha256_of(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_measure(path):
    """Returns (frame_count, fps, duration_seconds) measured directly via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,nb_frames",
        "-show_entries", "format=duration",
        "-of", "json", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    duration = float(data["format"]["duration"])

    num, den = stream["r_frame_rate"].split("/")
    fps = float(num) / float(den)

    nb_frames = stream.get("nb_frames")
    if nb_frames and nb_frames != "N/A":
        frame_count = int(nb_frames)
    else:
        frame_count = round(duration * fps)

    return frame_count, fps, duration


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--videos-dir", type=Path, required=True,
                         help="Folder containing your copies of the MSC movie files (named as in MSC/msc_movies.csv's fileName column).")
    parser.add_argument("--frame-tolerance", type=int, default=DEFAULT_FRAME_TOLERANCE,
                         help=f"Max frame-count difference to still count as PASS via ffprobe fallback (default: {DEFAULT_FRAME_TOLERANCE}).")
    parser.add_argument("--report-out", type=Path, default=None,
                         help="Optional path to also write the report as CSV.")
    args = parser.parse_args()

    manifest = load_csv(MSC / "msc_manifest.csv")
    movies = {r["imdb_id"]: r for r in load_csv(MSC / "msc_movies.csv")}
    checksums = {r["imdb_id"]: r["sha256"] for r in load_csv(MSC / "msc_checksums.csv")}
    ffprobe_ref = {r["video_id"]: r for r in load_csv(MSC / "msc_ffprobe_verification.csv")}

    results = []
    for row in manifest:
        imdb_id = row["imdb_id"]
        msc_id = row["msc_id"]
        movie_title = row["movie_title"]
        video_id = msc_id.split("_")[-1].lstrip("0") or "0"
        file_name = movies[imdb_id]["fileName"]
        candidate = args.videos_dir / file_name

        entry = {
            "msc_id": msc_id, "movie_title": movie_title, "file_name": file_name,
            "status": None, "reason": "",
        }

        if not candidate.is_file():
            entry["status"] = "FAIL"
            entry["reason"] = "file not found in --videos-dir"
            results.append(entry)
            continue

        expected_sha256 = checksums.get(imdb_id)
        actual_sha256 = sha256_of(candidate)
        if expected_sha256 and actual_sha256 == expected_sha256:
            entry["status"] = "PASS"
            entry["reason"] = "sha256 exact match"
            results.append(entry)
            continue

        try:
            frame_count, fps, duration = ffprobe_measure(candidate)
        except (subprocess.CalledProcessError, FileNotFoundError, KeyError, IndexError) as e:
            entry["status"] = "FAIL"
            entry["reason"] = f"ffprobe failed: {e}"
            results.append(entry)
            continue

        ref = ffprobe_ref.get(video_id)
        if ref is None:
            entry["status"] = "FAIL"
            entry["reason"] = f"no ffprobe reference for video_id {video_id}"
            results.append(entry)
            continue

        ref_frames = int(float(ref["ffprobe_nb_frames_tag"])) if ref["ffprobe_nb_frames_tag"] not in ("", "N/A") else round(float(ref["ffprobe_duration_seconds"]) * float(ref["ffprobe_r_frame_rate"]))
        ref_fps = float(ref["ffprobe_r_frame_rate"])

        frame_diff = abs(frame_count - ref_frames)
        fps_diff = abs(fps - ref_fps)

        if frame_diff <= args.frame_tolerance and fps_diff <= DEFAULT_FPS_TOLERANCE:
            entry["status"] = "PASS"
            entry["reason"] = f"checksum differs (different encode), but ffprobe matches within tolerance (frame diff={frame_diff}, fps diff={fps_diff:.4f})"
        else:
            entry["status"] = "FAIL"
            entry["reason"] = (f"checksum differs AND ffprobe mismatch: "
                                f"frames {frame_count} vs expected {ref_frames} (diff={frame_diff}), "
                                f"fps {fps:.3f} vs expected {ref_fps:.3f} (diff={fps_diff:.4f})")
        results.append(entry)

    results.sort(key=lambda r: r["movie_title"])

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")

    print(f"{'MSC ID':<10} {'Status':<6} {'Movie':<45} Reason")
    print("-" * 100)
    for r in results:
        print(f"{r['msc_id']:<10} {r['status']:<6} {r['movie_title']:<45} {r['reason']}")
    print("-" * 100)
    print(f"TOTAL: {n_pass} PASS, {n_fail} FAIL, out of {len(results)} movies")

    if args.report_out:
        with open(args.report_out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["msc_id", "movie_title", "file_name", "status", "reason"])
            writer.writeheader()
            writer.writerows(results)
        print(f"Report written to {args.report_out}")

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
