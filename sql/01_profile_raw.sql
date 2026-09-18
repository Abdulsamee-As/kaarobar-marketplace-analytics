-- =====================================================================
-- 01_profile_raw.sql : profile the raw extracts before changing anything
-- Each query is saved to outputs/profile_<name>.csv by src/run_pipeline.py.
-- The findings drive every rule in 02_clean.sql.
-- =====================================================================

-- name: data_quality_scorecard
-- One row per check: how many rows break an expectation.
SELECT 'orders' AS table_name, 'rows' AS check_name, COUNT(*) AS rows_affected FROM raw.orders
UNION ALL
SELECT 'orders', 'exact duplicate rows (ingestion retry)',
       COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw.orders) d) FROM raw.orders
UNION ALL
SELECT 'orders', 'legacy date format DD/MM/YYYY HH:MI',
       COUNT(*) FILTER (WHERE order_datetime LIKE '__/__/____ __:__') FROM raw.orders
UNION ALL
SELECT 'orders', 'blank shipping_city',
       COUNT(*) FILTER (WHERE shipping_city IS NULL OR TRIM(shipping_city) = '') FROM raw.orders
UNION ALL
SELECT 'orders', 'distinct spellings of shipping_city', COUNT(DISTINCT shipping_city) FROM raw.orders
UNION ALL
SELECT 'orders', 'distinct payment_method labels', COUNT(DISTINCT payment_method) FROM raw.orders
UNION ALL
SELECT 'orders', 'distinct order_status labels', COUNT(DISTINCT order_status) FROM raw.orders
UNION ALL
SELECT 'orders', 'shipping_fee stored as text like Rs. 150',
       COUNT(*) FILTER (WHERE shipping_fee LIKE 'Rs.%') FROM raw.orders
UNION ALL
SELECT 'orders', 'delivered status but blank delivered_at',
       COUNT(*) FILTER (WHERE LOWER(TRIM(order_status)) IN ('dlvd', 'delivered')
                          AND (delivered_at IS NULL OR TRIM(delivered_at) = '')) FROM raw.orders
UNION ALL
SELECT 'orders', 'orders from QA test accounts',
       COUNT(*) FILTER (WHERE customer_id LIKE 'TEST%') FROM raw.orders
UNION ALL
SELECT 'customers', 'duplicate accounts (same email after trim and lower-case)',
       COUNT(*) - COUNT(DISTINCT LOWER(TRIM(email))) FROM raw.customers
UNION ALL
SELECT 'customers', 'blank signup_date',
       COUNT(*) FILTER (WHERE signup_date IS NULL OR TRIM(signup_date) = '') FROM raw.customers
UNION ALL
SELECT 'products', 'distinct spellings of category', COUNT(DISTINCT category) FROM raw.products
UNION ALL
SELECT 'order_items', 'quantity zero or negative',
       COUNT(*) FILTER (WHERE CAST(quantity AS INTEGER) <= 0) FROM raw.order_items
UNION ALL
SELECT 'order_items', 'unit_price above 5x list price (extra zero typed)',
       COUNT(*) FILTER (WHERE CAST(i.unit_price AS NUMERIC(12, 2)) > 5 * CAST(p.list_price AS NUMERIC(12, 2)))
FROM raw.order_items i JOIN raw.products p ON p.product_id = i.product_id
UNION ALL
SELECT 'returns', 'orphan returns (order_item_id not found)',
       COUNT(*) FILTER (WHERE i.order_item_id IS NULL)
FROM raw.returns r LEFT JOIN raw.order_items i ON i.order_item_id = r.order_item_id
UNION ALL
SELECT 'checkout_sessions', 'duplicate session rows',
       COUNT(*) - COUNT(DISTINCT session_id) FROM raw.checkout_sessions
UNION ALL
SELECT 'checkout_sessions', 'sessions under 3 seconds (likely bots)',
       COUNT(*) FILTER (WHERE CAST(session_duration_sec AS INTEGER) < 3) FROM raw.checkout_sessions
UNION ALL
SELECT 'checkout_sessions', 'distinct experiment_group labels', COUNT(DISTINCT experiment_group) FROM raw.checkout_sessions;

-- name: city_spellings
-- Every raw spelling of a city, to build the lookup table in 02_clean.sql.
SELECT shipping_city AS raw_city, COUNT(*) AS orders
FROM raw.orders
GROUP BY shipping_city
ORDER BY orders DESC;

-- name: label_inventory
-- Every raw label used for payment, status, and experiment group.
SELECT 'payment_method' AS field, payment_method AS raw_value, COUNT(*) AS rows_count FROM raw.orders GROUP BY payment_method
UNION ALL
SELECT 'order_status', order_status, COUNT(*) FROM raw.orders GROUP BY order_status
UNION ALL
SELECT 'experiment_group', experiment_group, COUNT(*) FROM raw.checkout_sessions GROUP BY experiment_group
UNION ALL
SELECT 'category', category, COUNT(*) FROM raw.products GROUP BY category
ORDER BY field, rows_count DESC;
