-- SQLite warehouse definition and load.
-- Requires stg_restaurants, stg_restaurant_reports, stg_orders and
-- stg_order_items, loaded by build_curated.py from lake/raw. Re-running this
-- script rebuilds the final tables and view from those staging tables.

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

DROP VIEW IF EXISTS restaurant_sales;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS restaurant_reports;
DROP TABLE IF EXISTS restaurants;

CREATE TABLE restaurants (
    restaurant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE restaurant_reports (
    report_id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(restaurant_id),
    report_date TEXT NOT NULL,
    order_count INTEGER NOT NULL,
    gross_sales REAL NOT NULL,
    batch_id TEXT NOT NULL
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES restaurant_reports(report_id),
    restaurant_id TEXT NOT NULL REFERENCES restaurants(restaurant_id),
    price REAL NOT NULL,
    rider_id TEXT NOT NULL,
    rider_name TEXT NOT NULL,
    rider_fee REAL NOT NULL,
    food_dash_cut REAL NOT NULL,
    batch_id TEXT NOT NULL
);

CREATE TABLE order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    dish TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    total_price REAL NOT NULL
);

-- A restaurant can appear in several reports; use the latest delivered name.
WITH ranked AS (
    SELECT restaurant_id, TRIM(name) AS name,
           ROW_NUMBER() OVER (
               PARTITION BY restaurant_id ORDER BY batch_id DESC, report_id DESC
           ) AS row_number
    FROM stg_restaurants
)
INSERT INTO restaurants (restaurant_id, name)
SELECT restaurant_id, name FROM ranked WHERE row_number = 1;

INSERT OR REPLACE INTO restaurant_reports
    (report_id, restaurant_id, report_date, order_count, gross_sales, batch_id)
SELECT report_id, restaurant_id, report_date,
       CAST(order_count AS INTEGER), CAST(gross_sales AS REAL), batch_id
FROM stg_restaurant_reports;

INSERT OR REPLACE INTO orders
    (order_id, report_id, restaurant_id, price, rider_id, rider_name,
     rider_fee, food_dash_cut, batch_id)
SELECT order_id, report_id, restaurant_id, CAST(price AS REAL), rider_id,
       TRIM(rider_name), CAST(rider_fee AS REAL), CAST(food_dash_cut AS REAL), batch_id
FROM stg_orders;

INSERT OR REPLACE INTO order_items
    (order_item_id, order_id, dish, quantity, total_price)
SELECT order_item_id, order_id, TRIM(dish), CAST(quantity AS INTEGER),
       CAST(total_price AS REAL)
FROM stg_order_items;

CREATE INDEX idx_reports_restaurant ON restaurant_reports(restaurant_id);
CREATE INDEX idx_orders_restaurant ON orders(restaurant_id);
CREATE INDEX idx_items_order ON order_items(order_id);

CREATE VIEW restaurant_sales AS
SELECT r.restaurant_id, r.name,
       COUNT(o.order_id) AS order_count,
       COALESCE(ROUND(SUM(o.price), 2), 0) AS gross_sales
FROM restaurants AS r
LEFT JOIN orders AS o ON o.restaurant_id = r.restaurant_id
GROUP BY r.restaurant_id, r.name;

COMMIT;
PRAGMA foreign_keys = ON;
