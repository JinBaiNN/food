# FoodDash sample pipeline

This repository simulates three sources: GPS events, restaurant reports, and
customer feedback. Run the scripts in order from the repository root:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python generate_raw.py --rows 20
.venv/bin/python ingest_raw.py
.venv/bin/python build_curated.py
```

`--rows` controls the number of records **per feed**; for example, use
`--rows 1000` to generate a larger batch. `--seed` changes the sample values.
Every generator run creates a new folder under `landing_zone/` containing the
three raw files and a `_READY` marker. The ingester reads only complete batches,
checks required columns, and copies the files unchanged to `lake/raw/` with a
manifest. Rerunning ingestion skips batches already copied; it rejects a
changed source batch with the same ID.

`build_curated.py` reads all ingested batches and writes:

| Path | Contents |
| --- | --- |
| `lake/processed/gps_events.csv` | GPS events with invalid coordinates/times removed |
| `warehouse/restaurants.db` | Generated restaurant warehouse |
| `warehouse/customer_feedback.db` | Generated feedback warehouse |

The reusable warehouse definitions and loads are in `sql/restaurants.sql` and
`sql/customer_feedback.sql`. The builder loads source rows into SQLite staging
tables (`stg_restaurants`, `stg_restaurant_reports`, `stg_orders`,
`stg_order_items`, and `stg_feedback`) and executes those SQL files to create
the final tables, indexes, and summary views. The staging tables remain in the
generated databases, so each SQL file can be run again against its database.
The `.sql` files are the maintained source; the `.db` files are generated outputs
and are ignored by Git. Use `--sql-dir` to run the builder with another directory
containing compatible SQL definitions.

The curated step rebuilds these outputs from the raw lake, so rerunning it does
not duplicate rows. It trims display text in the warehouses while the raw lake
retains the source values. GPS is represented as batches of timestamped events;
`udp_connection.py` is an independent UDP example and is not required to run
this file-based pipeline.

Run the pipeline checks with `.venv/bin/python -m unittest discover -s tests -v`.
The repository includes a 20-row sample delivery at `landing_zone/demo_001/`.

For alternate locations, use `--landing-zone` with the generator and ingester,
`--lake` with the ingester and curated builder, and `--warehouse` with the
curated builder. The [contract](contract.md) defines all fields and delivery rules.
