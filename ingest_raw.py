"""Validate landing batches with Pandas and preserve them in the raw lake."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
FEEDS = {
    "gps.csv": {"gps_id", "rider_id", "order_id", "lat", "long", "timestamp"},
    "restaurant_reports.jsonl": {
        "report_id", "restaurant_id", "name", "report_date", "orders"
    },
    "customer_feedback.csv": {
        "feedback_id", "restaurant_id", "restaurant_name", "order_id",
        "customer_id", "rating", "complaint", "created_at"
    },
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_file(path: Path, required_columns: set[str]) -> dict:
    if path.suffix == ".jsonl":
        frame = pd.read_json(path, lines=True)
    else:
        frame = pd.read_csv(path)
    actual_columns = {str(column).strip() for column in frame.columns}
    missing = required_columns - actual_columns
    if missing:
        raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError(f"{path}: empty feed")
    return {"rows": len(frame), "sha256": file_hash(path)}


def ingest(landing_zone: Path, lake: Path) -> tuple[int, int]:
    if not landing_zone.exists():
        print(f"No landing zone at {landing_zone}")
        return 0, 0
    raw_root = lake / "raw"
    ingested = 0
    skipped = 0
    for batch_dir in sorted(landing_zone.iterdir()):
        if not batch_dir.is_dir() or not (batch_dir / "_READY").is_file():
            continue
        missing_files = [name for name in FEEDS if not (batch_dir / name).is_file()]
        if missing_files:
            print(f"Skipping {batch_dir.name}: missing {', '.join(missing_files)}")
            skipped += 1
            continue

        manifest = {
            "batch_id": batch_dir.name,
            "files": {
                name: inspect_file(batch_dir / name, columns)
                for name, columns in FEEDS.items()
            },
        }
        destination = raw_root / batch_dir.name
        if destination.exists():
            if all(
                (destination / name).is_file()
                and file_hash(destination / name) == info["sha256"]
                for name, info in manifest["files"].items()
            ):
                print(f"Already ingested {batch_dir.name}")
                skipped += 1
                continue
            raise ValueError(f"{destination} differs from landing batch; raw batches are immutable")

        raw_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{batch_dir.name}.", dir=raw_root) as temp_dir:
            staged = Path(temp_dir)
            for name in FEEDS:
                shutil.copy2(batch_dir / name, staged / name)
            (staged / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            staged.rename(destination)
        print(f"Ingested {batch_dir.name}: " + ", ".join(
            f"{name}={info['rows']}" for name, info in manifest["files"].items()
        ))
        ingested += 1
    return ingested, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--landing-zone", type=Path, default=ROOT / "landing_zone")
    parser.add_argument("--lake", type=Path, default=ROOT / "lake")
    args = parser.parse_args()
    count, skipped = ingest(args.landing_zone, args.lake)
    print(f"Done: {count} ingested, {skipped} skipped")


if __name__ == "__main__":
    main()
