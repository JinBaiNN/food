"""End-to-end checks for the file handoff and curated outputs."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from build_curated import build
from generate_raw import generate
from ingest_raw import file_hash, ingest


class PipelineTest(unittest.TestCase):
    def test_complete_batch_and_idempotent_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            landing = root / "landing_zone"
            lake = root / "lake"
            warehouse = root / "warehouse"
            batch = generate(20, 42, landing, "test_001")

            self.assertEqual(ingest(landing, lake), (1, 0))
            self.assertEqual(ingest(landing, lake), (0, 1))
            raw = lake / "raw" / "test_001"
            for filename in ("gps.csv", "restaurant_reports.jsonl", "customer_feedback.csv"):
                self.assertEqual(file_hash(batch / filename), file_hash(raw / filename))

            counts = build(lake, warehouse)
            self.assertEqual(counts["restaurant_reports"], 20)
            self.assertEqual(counts["feedback"], 20)
            self.assertEqual(counts["gps_events"], 19)  # One intentionally missing latitude.
            with sqlite3.connect(warehouse / "restaurants.db") as connection:
                order_count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                self.assertGreaterEqual(order_count, 20)
                summary_count = connection.execute(
                    "SELECT COUNT(*) FROM restaurant_sales"
                ).fetchone()[0]
                self.assertEqual(summary_count, counts["restaurants"])
                # The checked-in SQL can rebuild the warehouse from retained staging.
                sql = (Path(__file__).resolve().parents[1] / "sql" / "restaurants.sql").read_text()
                connection.executescript(sql)
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
                    order_count,
                )
            with sqlite3.connect(warehouse / "customer_feedback.db") as connection:
                feedback_count = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
                self.assertEqual(feedback_count, 20)
                self.assertEqual(
                    connection.execute("SELECT SUM(feedback_count) FROM feedback_summary").fetchone()[0],
                    20,
                )

            self.assertEqual(build(lake, warehouse), counts)
            gps = pd.read_csv(lake / "processed" / "gps_events.csv")
            self.assertEqual(len(gps), 19)
            self.assertTrue(gps["lat"].notna().all())

    def test_missing_file_is_skipped_until_batch_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            landing = root / "landing_zone"
            lake = root / "lake"
            batch = generate(10, 1, landing, "test_002")
            feedback = batch / "customer_feedback.csv"
            saved = feedback.read_bytes()
            feedback.unlink()
            self.assertEqual(ingest(landing, lake), (0, 1))
            self.assertFalse((lake / "raw" / "test_002").exists())
            feedback.write_bytes(saved)
            self.assertEqual(ingest(landing, lake), (1, 0))


if __name__ == "__main__":
    unittest.main()
