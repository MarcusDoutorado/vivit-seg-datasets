#!/usr/bin/env python3
"""Builds MSC/msc_manifest.csv (and .json) from the source CSVs already in MSC/.

Joins, per verified movie (the 54-video MSC-trust set):
  - msc_movies.csv            -> msc_id, imdb_id, movie_title
  - table_msc_dataset_info.csv -> bbfc_release_version, bbfc_runtime, frame_count, shot_count, scene_count
  - msc_ffprobe_verification.csv -> fps (measured directly via ffprobe on our own copy)

Run from the repo root:
    python3 scripts/generate_msc_manifest.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MSC = ROOT / "MSC"


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    movies = {r["imdb_id"]: r for r in load_csv(MSC / "msc_movies.csv")}
    info = {r["imdb"]: r for r in load_csv(MSC / "table_msc_dataset_info.csv") if r["imdb"]}
    ffprobe = {r["video_id"]: r for r in load_csv(MSC / "msc_ffprobe_verification.csv")}

    rows = []
    for imdb_id, info_row in info.items():
        movie_row = movies.get(imdb_id)
        if movie_row is None:
            raise SystemExit(f"imdb_id {imdb_id} in table_msc_dataset_info.csv not found in msc_movies.csv")
        msc_id = movie_row["msc_id"]
        video_id = msc_id.split("_")[-1].lstrip("0") or "0"
        ffprobe_row = ffprobe.get(video_id)
        if ffprobe_row is None:
            raise SystemExit(f"video_id {video_id} ({msc_id}) not found in msc_ffprobe_verification.csv")

        rows.append({
            "msc_id": msc_id,
            "imdb_id": imdb_id,
            "movie_title": movie_row["primaryTitle"],
            "bbfc_release_version": info_row["bbfc_version"],
            "bbfc_runtime": info_row["duration"],
            "fps": round(float(ffprobe_row["ffprobe_r_frame_rate"]), 3),
            "frame_count": int(info_row["frames"]),
            "shot_count": int(info_row["shots"]),
            "scene_count": int(info_row["scenes"]),
        })

    rows.sort(key=lambda r: r["movie_title"])

    fieldnames = ["msc_id", "imdb_id", "movie_title", "bbfc_release_version", "bbfc_runtime",
                  "fps", "frame_count", "shot_count", "scene_count"]

    out_csv = MSC / "msc_manifest.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    out_json = MSC / "msc_manifest.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {len(rows)} movies to {out_csv} and {out_json}")


if __name__ == "__main__":
    main()
