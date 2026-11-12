"""Process raw GPS events and load the SQL-defined SQLite warehouses."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent


def build(lake: Path, warehouse: Path, sql_dir: Path = ROOT / "sql") -> dict[str, int]:
    raw_root = lake / "raw"
    batches = sorted(path for path in raw_root.iterdir() if (path / "manifest.json").is_file()) \
        if raw_root.exists() else []
    if not batches:
        print(f"No ingested batches in {raw_root}")
        return {}

    gps_frames = []
    feedback_frames = []
    restaurant_rows = []
    report_rows = []
    order_rows = []
    item_rows = []
    for batch in batches:
        gps = pd.read_csv(batch / "gps.csv")
        gps.columns = gps.columns.str.strip()
        gps["batch_id"] = batch.name
        gps_frames.append(gps)

        feedback = pd.read_csv(batch / "customer_feedback.csv")
        feedback.columns = feedback.columns.str.strip()
        feedback["batch_id"] = batch.name
        feedback_frames.append(feedback)

        reports = pd.read_json(batch / "restaurant_reports.jsonl", lines=True)
        reports.columns = reports.columns.str.strip()
        for report in reports.to_dict("records"):
            restaurant_id = str(report["restaurant_id"])
            restaurant_rows.append({
                "restaurant_id": restaurant_id,
                "name": str(report["name"]),
                "report_id": report["report_id"],
                "batch_id": batch.name,
            })
            orders = report["orders"]
            report_rows.append({
                "report_id": report["report_id"],
                "restaurant_id": restaurant_id,
                "report_date": report["report_date"],
                "order_count": len(orders),
                "gross_sales": round(sum(float(order["price"]) for order in orders), 2),
                "batch_id": batch.name,
            })
            for order in orders:
                order_rows.append({
                    "order_id": order["id"],
                    "report_id": report["report_id"],
                    "restaurant_id": restaurant_id,
                    "price": float(order["price"]),
                    "rider_id": order["rider_id"],
                    "rider_name": order["rider_name"],
                    "rider_fee": float(order["rider_fee"]),
                    "food_dash_cut": float(order["food_dash_cut"]),
                    "batch_id": batch.name,
                })
                for index, item in enumerate(order["contents"], start=1):
                    item_rows.append({
                        "order_item_id": f"{order['id']}_{index}",
                        "order_id": order["id"],
                        "dish": item["dish"],
                        "quantity": int(item["quantity"]),
                        "total_price": float(item["total_price"]),
                    })

    gps = pd.concat(gps_frames, ignore_index=True)
    gps["lat"] = pd.to_numeric(gps["lat"], errors="coerce")
    gps["long"] = pd.to_numeric(gps["long"], errors="coerce")
    gps["timestamp"] = pd.to_datetime(gps["timestamp"], errors="coerce", utc=True)
    gps = gps.loc[
        gps["lat"].between(-90, 90)
        & gps["long"].between(-180, 180)
        & gps["timestamp"].notna()
    ].drop_duplicates("gps_id")
    gps["timestamp"] = gps["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    gps = gps.sort_values("timestamp")
    processed_dir = lake / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    gps.to_csv(processed_dir / "gps_events.csv", index=False)

    restaurants = pd.DataFrame(restaurant_rows)
    reports = pd.DataFrame(report_rows)
    orders = pd.DataFrame(order_rows)
    items = pd.DataFrame(item_rows)
    feedback = pd.concat(feedback_frames, ignore_index=True)

    warehouse.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(warehouse / "restaurants.db") as connection:
        restaurants.to_sql("stg_restaurants", connection, if_exists="replace", index=False)
        reports.to_sql("stg_restaurant_reports", connection, if_exists="replace", index=False)
        orders.to_sql("stg_orders", connection, if_exists="replace", index=False)
        items.to_sql("stg_order_items", connection, if_exists="replace", index=False)
        connection.executescript((sql_dir / "restaurants.sql").read_text(encoding="utf-8"))
        restaurant_count = connection.execute("SELECT COUNT(*) FROM restaurants").fetchone()[0]
        report_count = connection.execute("SELECT COUNT(*) FROM restaurant_reports").fetchone()[0]
        order_count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    with sqlite3.connect(warehouse / "customer_feedback.db") as connection:
        feedback.to_sql("stg_feedback", connection, if_exists="replace", index=False)
        connection.executescript((sql_dir / "customer_feedback.sql").read_text(encoding="utf-8"))
        feedback_count = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

    counts = {
        "gps_events": len(gps),
        "restaurants": restaurant_count,
        "restaurant_reports": report_count,
        "orders": order_count,
        "feedback": feedback_count,
    }
    print("Built curated data: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", type=Path, default=ROOT / "lake")
    parser.add_argument("--warehouse", type=Path, default=ROOT / "warehouse")
    parser.add_argument("--sql-dir", type=Path, default=ROOT / "sql")
    args = parser.parse_args()
    build(args.lake, args.warehouse, args.sql_dir)


if __name__ == "__main__":
    main()
