"""Generate a batch of deliberately imperfect FoodDash source data."""

from __future__ import annotations

import argparse
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
RESTAURANT_NAMES = (
    "Olive Garden", "Curry House", "Noodle Kitchen", "Pizza Corner",
    "The Green Bowl", "Taco Station", "Sushi Room", "Burger Place",
)
DISHES = ("Margherita", "Ramen", "Rice bowl", "Burrito", "Salad", "Curry")
COMPLAINTS = (
    "Food arrived cold", "Late delivery", "Wrong item", "Missing sauce",
    "Great meal", "Packaging was damaged", "Portion was small",
)


def valid_batch_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise argparse.ArgumentTypeError("batch ID may contain only letters, digits, _ and -")
    return value


def generate(rows: int, seed: int, landing_zone: Path, batch_id: str | None = None) -> Path:
    if rows < 1:
        raise ValueError("rows must be at least 1")
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    batch_id = valid_batch_id(batch_id or now.strftime("%Y%m%dT%H%M%S%fZ"))
    batch_dir = landing_zone / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)

    restaurant_count = min(max(3, rows // 2), 50)
    reports: list[dict] = []
    order_refs: list[tuple[str, str, str, str]] = []
    order_number = 0
    for i in range(rows):
        restaurant_number = i % restaurant_count
        restaurant_id = f"rest_{restaurant_number + 1:04d}"
        name = RESTAURANT_NAMES[restaurant_number % len(RESTAURANT_NAMES)]
        if restaurant_number >= len(RESTAURANT_NAMES):
            name += f" {restaurant_number // len(RESTAURANT_NAMES) + 1}"
        if i % 17 == 0:
            name = f"  {name}  "
        elif i % 19 == 0:
            name = name.upper()

        orders = []
        for _ in range(rng.randint(1, 3)):
            order_number += 1
            order_id = f"ord_{batch_id}_{order_number:06d}"
            rider_id = f"rider_{order_number % 12 + 1:04d}"
            contents = []
            for _ in range(rng.randint(1, 2)):
                quantity = rng.randint(1, 3)
                unit_price = rng.choice((6.5, 8.75, 10.0, 12.25, 14.5))
                contents.append({
                    "dish": rng.choice(DISHES),
                    "quantity": quantity,
                    "total_price": round(quantity * unit_price, 2),
                })
            orders.append({
                "id": order_id,
                "contents": contents,
                "price": round(sum(item["total_price"] for item in contents), 2),
                "rider_id": rider_id,
                "rider_name": f"Rider {order_number % 12 + 1}",
                "rider_fee": round(rng.uniform(2.0, 5.0), 2),
                "food_dash_cut": round(rng.uniform(1.0, 4.0), 2),
            })
            order_refs.append((order_id, rider_id, restaurant_id, name))
        reports.append({
            "report_id": f"report_{batch_id}_{i + 1:06d}",
            "restaurant_id": restaurant_id,
            "name": name,
            "report_date": (now - timedelta(days=i % 7)).date().isoformat(),
            "orders": orders,
        })

    gps = []
    feedback = []
    for i in range(rows):
        order_id, rider_id, restaurant_id, restaurant_name = order_refs[i % len(order_refs)]
        gps.append({
            "gps_id": f"gps_{batch_id}_{i + 1:06d}",
            "rider_id": rider_id,
            "order_id": order_id,
            "lat": None if rows >= 20 and i == 7 else round(51.50 + rng.uniform(-0.06, 0.06), 6),
            "long": round(-0.12 + rng.uniform(-0.08, 0.08), 6),
            "timestamp": (now - timedelta(seconds=(rows - i) * 5)).isoformat(),
        })
        complaint = rng.choice(COMPLAINTS)
        if i % 11 == 0:
            complaint = f"  {complaint.upper()}  "
        if rows >= 20 and i == 13:
            complaint = None
        feedback.append({
            "feedback_id": f"feedback_{batch_id}_{i + 1:06d}",
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant_name,
            "order_id": order_id,
            "customer_id": f"customer_{i % max(3, rows // 2) + 1:04d}",
            "rating": rng.randint(1, 5),
            "complaint": complaint,
            "created_at": (now + timedelta(minutes=i)).isoformat(),
        })

    pd.DataFrame(gps).to_csv(batch_dir / "gps.csv", index=False)
    pd.DataFrame(reports).to_json(
        batch_dir / "restaurant_reports.jsonl", orient="records", lines=True, force_ascii=False
    )
    pd.DataFrame(feedback).to_csv(batch_dir / "customer_feedback.csv", index=False)
    # The marker is written last, so ingestion never reads an unfinished batch.
    (batch_dir / "_READY").touch()
    return batch_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=20, help="records per feed (default: 20)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--landing-zone", type=Path, default=ROOT / "landing_zone")
    parser.add_argument("--batch-id", type=valid_batch_id)
    args = parser.parse_args()
    print(f"Created {generate(args.rows, args.seed, args.landing_zone, args.batch_id)}")


if __name__ == "__main__":
    main()
