#!/usr/bin/env python3
"""Generates docs/download_guide.md: per-movie release info + a reference
SHA-256 checksum, so someone who has independently sourced a copy of each
MSC movie can check whether it matches the specific release we used.

We do not redistribute the source videos (copyright) -- this only tells you
which release we matched (via the BBFC cross-check, see docs/methodology.md)
and what its checksum should be, so you can confirm your own copy is
equivalent before trusting shots.csv/scenes.csv against it.

Usage:
    python3 scripts/generate_download_guide.py --videos-dir /path/to/your/msc/videos

The videos directory is expected to contain the files named in
MSC/msc_movies.csv's `fileName` column (case-sensitive, exact match). Movies
whose file isn't found in --videos-dir are still listed, with the checksum
column left as "not computed" -- run the script again once you have that
file to fill it in.

Also writes MSC/msc_checksums.csv (imdb_id, file_name, sha256), the
machine-readable counterpart of the same table, consumed by
scripts/verify_msc_download.py.
"""
import argparse
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MSC = ROOT / "MSC"
DOCS = ROOT / "docs"


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha256_of(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--videos-dir", type=Path, default=None,
                         help="Folder containing your copies of the MSC movie files, to compute reference checksums from.")
    args = parser.parse_args()

    manifest = {r["imdb_id"]: r for r in load_csv(MSC / "msc_manifest.csv")}
    movies = {r["imdb_id"]: r for r in load_csv(MSC / "msc_movies.csv")}

    rows = []
    for imdb_id, m in manifest.items():
        movie_row = movies[imdb_id]
        file_name = movie_row["fileName"]
        checksum = "not computed"
        if args.videos_dir is not None:
            candidate = args.videos_dir / file_name
            if candidate.is_file():
                checksum = sha256_of(candidate)
            else:
                checksum = "file not found in --videos-dir"
        rows.append({
            "movie_title": m["movie_title"],
            "imdb_id": imdb_id,
            "bbfc_release_version": m["bbfc_release_version"],
            "file_name": file_name,
            "sha256": checksum,
        })

    rows.sort(key=lambda r: r["movie_title"])

    lines = [
        "# MSC download guide",
        "",
        "We do not redistribute the source videos (copyright). This table documents,",
        "per movie, the specific commercial release our own copy corresponds to",
        "(identified via the BBFC cross-check, see `docs/methodology.md`) and a",
        "reference SHA-256 checksum, so you can confirm a release you have sourced",
        "independently is equivalent before trusting our shot/scene boundaries",
        "(`MSC/shots_trust.csv` / `MSC/scenes_trust.csv`) against it.",
        "",
        "A checksum match means byte-identical files. A mismatch does not",
        "necessarily mean incompatibility -- re-encodes/remuxes of the same cut",
        "commonly change the checksum without changing frame content -- but it does",
        "mean you should spot-check against `MSC/verification_frames/` before",
        "assuming alignment with `shots_trust.csv`/`scenes_trust.csv`.",
        "",
        "| Movie | IMDb ID | Matched release (BBFC) | Expected filename | SHA-256 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['movie_title']} | {r['imdb_id']} | {r['bbfc_release_version']} | `{r['file_name']}` | `{r['sha256']}` |")
    lines.append("")

    DOCS.mkdir(exist_ok=True)
    out_path = DOCS / "download_guide.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")

    checksums_path = MSC / "msc_checksums.csv"
    with open(checksums_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["imdb_id", "file_name", "sha256"])
        writer.writeheader()
        for r in rows:
            writer.writerow({"imdb_id": r["imdb_id"], "file_name": r["file_name"], "sha256": r["sha256"]})

    print(f"Wrote {len(rows)} movies to {out_path} and {checksums_path}")


if __name__ == "__main__":
    main()
