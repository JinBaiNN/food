# FoodDash raw data contract

Each producer run writes one immutable batch to `landing_zone/<batch_id>/`.
The batch is complete when `_READY` exists. The producer publishes batches on
demand; each run is a new delivery. All three feeds are included in every batch.
The ingester validates them with Pandas and copies the original bytes to
`lake/raw/<batch_id>/`. `manifest.json` records row counts and SHA-256 hashes.

IDs are strings and are never parsed as numbers. Timestamps are ISO 8601 with a
UTC offset. Monetary values are decimal numbers in GBP; this sample uses
two decimal places. Source strings may have extra spaces or mixed casing.

## GPS events: `gps.csv`

One row is one rider location event. This is a micro-batch representation of a
stream; each new batch delivers more events.

| Column | Type | Meaning |
| --- | --- | --- |
| `gps_id` | string | Unique event ID |
| `rider_id` | string | Rider ID |
| `order_id` | string | Related order ID |
| `lat` | number, nullable | Latitude in degrees |
| `long` | number | Longitude in degrees |
| `timestamp` | ISO 8601 string | Event time in UTC |

## Restaurant reports: `restaurant_reports.jsonl`

One JSON object per line. Each row is a report for one restaurant and contains
one or more orders. `report_id` and order `id` are unique. This is valid JSONL:

```json
{"report_id":"report_demo_000001","restaurant_id":"rest_0001","name":"Olive Garden","report_date":"2026-11-12","orders":[{"id":"ord_demo_000001","contents":[{"dish":"Salad","quantity":2,"total_price":17.50}],"price":17.50,"rider_id":"rider_0001","rider_name":"Rider 1","rider_fee":3.20,"food_dash_cut":2.10}]}
```

| Field | Type |
| --- | --- |
| `report_id`, `restaurant_id`, `name` | string |
| `report_date` | `YYYY-MM-DD` string |
| `orders` | array of order objects |
| `orders[].id`, `orders[].rider_id`, `orders[].rider_name` | string |
| `orders[].price`, `orders[].rider_fee`, `orders[].food_dash_cut` | number |
| `orders[].contents` | array of item objects |
| `orders[].contents[].dish` | string |
| `orders[].contents[].quantity` | integer |
| `orders[].contents[].total_price` | number |

## Customer feedback: `customer_feedback.csv`

One row is one customer feedback record. `restaurant_id` and `order_id` link
it to the restaurant reports.

| Column | Type | Meaning |
| --- | --- | --- |
| `feedback_id` | string | Unique feedback ID |
| `restaurant_id` | string | Related restaurant ID |
| `restaurant_name` | string | Source display name |
| `order_id` | string | Related order ID |
| `customer_id` | string | Customer ID |
| `rating` | integer | 1–5 stars |
| `complaint` | string, nullable | Free text feedback |
| `created_at` | ISO 8601 string | Feedback time in UTC |

The raw lake preserves source values. `build_curated.py` makes a processed GPS
file and executes the reusable SQL definitions in `sql/` to build separate
SQLite restaurant and feedback warehouses from ingested batches.
