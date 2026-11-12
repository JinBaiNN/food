-- SQLite warehouse definition and load.
-- Requires stg_feedback, loaded by build_curated.py from lake/raw. Re-running
-- this script rebuilds the final table and view from that staging table.

BEGIN TRANSACTION;

DROP VIEW IF EXISTS feedback_summary;
DROP TABLE IF EXISTS feedback;

CREATE TABLE feedback (
    feedback_id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL,
    restaurant_name TEXT NOT NULL,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    complaint TEXT,
    created_at TEXT NOT NULL,
    batch_id TEXT NOT NULL
);

INSERT OR REPLACE INTO feedback
    (feedback_id, restaurant_id, restaurant_name, order_id, customer_id,
     rating, complaint, created_at, batch_id)
SELECT feedback_id, restaurant_id, TRIM(restaurant_name), order_id,
       customer_id, CAST(rating AS INTEGER), NULLIF(TRIM(complaint), ''),
       created_at, batch_id
FROM stg_feedback;

CREATE INDEX idx_feedback_restaurant ON feedback(restaurant_id);
CREATE INDEX idx_feedback_order ON feedback(order_id);

CREATE VIEW feedback_summary AS
SELECT restaurant_id, COUNT(*) AS feedback_count,
       ROUND(AVG(rating), 2) AS average_rating,
       SUM(CASE WHEN complaint IS NOT NULL THEN 1 ELSE 0 END) AS comment_count
FROM feedback
GROUP BY restaurant_id;

COMMIT;
