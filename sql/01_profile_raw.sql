SELECT 'orders' AS table_name, 'rows' AS check_name, COUNT(*) AS rows_affected FROM raw.orders
UNION ALL
SELECT 'orders', 'exact duplicate rows (ingestion retry)',
       (SELECT COUNT(*) FROM raw.orders) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw.orders) d)
UNION ALL
SELECT 'orders', 'legacy date format DD/MM/YYYY HH:MI',
       SUM(CASE WHEN order_datetime LIKE '__/__/____ __:__' THEN 1 ELSE 0 END) FROM raw.orders
UNION ALL
SELECT 'orders', 'blank shipping_city',
       SUM(CASE WHEN shipping_city IS NULL OR TRIM(shipping_city) = '' THEN 1 ELSE 0 END) FROM raw.orders
UNION ALL
SELECT 'orders', 'distinct spellings of shipping_city',
       COUNT(DISTINCT (shipping_city + '|') COLLATE Latin1_General_BIN2) FROM raw.orders
UNION ALL
SELECT 'orders', 'distinct payment_method labels',
       COUNT(DISTINCT (payment_method + '|') COLLATE Latin1_General_BIN2) FROM raw.orders
UNION ALL
SELECT 'orders', 'distinct order_status labels',
       COUNT(DISTINCT (order_status + '|') COLLATE Latin1_General_BIN2) FROM raw.orders
UNION ALL
SELECT 'orders', 'shipping_fee stored as text like Rs. 150',
       SUM(CASE WHEN shipping_fee LIKE 'Rs.%' THEN 1 ELSE 0 END) FROM raw.orders
UNION ALL
SELECT 'orders', 'delivered status but blank delivered_at',
       SUM(CASE WHEN LOWER(TRIM(order_status)) IN ('dlvd', 'delivered')
                 AND (delivered_at IS NULL OR TRIM(delivered_at) = '') THEN 1 ELSE 0 END) FROM raw.orders
UNION ALL
SELECT 'orders', 'orders from QA test accounts',
       SUM(CASE WHEN customer_id LIKE 'TEST%' THEN 1 ELSE 0 END) FROM raw.orders
UNION ALL
SELECT 'customers', 'duplicate accounts (same email after trim and lower-case)',
       COUNT(*) - COUNT(DISTINCT LOWER(TRIM(email))) FROM raw.customers
UNION ALL
SELECT 'customers', 'blank signup_date',
       SUM(CASE WHEN signup_date IS NULL OR TRIM(signup_date) = '' THEN 1 ELSE 0 END) FROM raw.customers
UNION ALL
SELECT 'products', 'distinct spellings of category',
       COUNT(DISTINCT (category + '|') COLLATE Latin1_General_BIN2) FROM raw.products
UNION ALL
SELECT 'order_items', 'quantity zero or negative',
       SUM(CASE WHEN TRY_CONVERT(int, quantity) <= 0 THEN 1 ELSE 0 END) FROM raw.order_items
UNION ALL
SELECT 'order_items', 'unit_price above 5x list price (extra zero typed)',
       SUM(CASE WHEN TRY_CONVERT(decimal(14, 2), i.unit_price) > 5 * TRY_CONVERT(decimal(14, 2), p.list_price) THEN 1 ELSE 0 END)
FROM raw.order_items i JOIN raw.products p ON p.product_id = i.product_id
UNION ALL
SELECT 'returns', 'orphan returns (order_item_id not found)',
       SUM(CASE WHEN i.order_item_id IS NULL THEN 1 ELSE 0 END)
FROM raw.returns r LEFT JOIN raw.order_items i ON i.order_item_id = r.order_item_id
UNION ALL
SELECT 'checkout_sessions', 'duplicate session rows',
       COUNT(*) - COUNT(DISTINCT session_id) FROM raw.checkout_sessions
UNION ALL
SELECT 'checkout_sessions', 'sessions under 3 seconds (likely bots)',
       SUM(CASE WHEN TRY_CONVERT(int, session_duration_sec) < 3 THEN 1 ELSE 0 END) FROM raw.checkout_sessions
UNION ALL
SELECT 'checkout_sessions', 'distinct experiment_group labels',
       COUNT(DISTINCT (experiment_group + '|') COLLATE Latin1_General_BIN2) FROM raw.checkout_sessions;

SELECT raw_city, characters, orders
FROM (
    SELECT shipping_city COLLATE Latin1_General_BIN2 AS raw_city,
           DATALENGTH(shipping_city) / 2 AS characters,
           COUNT(*) AS orders
    FROM raw.orders
    GROUP BY shipping_city COLLATE Latin1_General_BIN2, DATALENGTH(shipping_city)
) spellings
ORDER BY orders DESC, CASE WHEN raw_city IS NULL THEN 1 ELSE 0 END, raw_city, characters;

SELECT field, raw_value, characters, rows_count
FROM (
    SELECT 'payment_method' AS field, payment_method COLLATE Latin1_General_BIN2 AS raw_value,
           DATALENGTH(payment_method) / 2 AS characters, COUNT(*) AS rows_count
    FROM raw.orders GROUP BY payment_method COLLATE Latin1_General_BIN2, DATALENGTH(payment_method)
    UNION ALL
    SELECT 'order_status', order_status COLLATE Latin1_General_BIN2,
           DATALENGTH(order_status) / 2, COUNT(*)
    FROM raw.orders GROUP BY order_status COLLATE Latin1_General_BIN2, DATALENGTH(order_status)
    UNION ALL
    SELECT 'experiment_group', experiment_group COLLATE Latin1_General_BIN2,
           DATALENGTH(experiment_group) / 2, COUNT(*)
    FROM raw.checkout_sessions GROUP BY experiment_group COLLATE Latin1_General_BIN2, DATALENGTH(experiment_group)
    UNION ALL
    SELECT 'category', category COLLATE Latin1_General_BIN2,
           DATALENGTH(category) / 2, COUNT(*)
    FROM raw.products GROUP BY category COLLATE Latin1_General_BIN2, DATALENGTH(category)
) labels
ORDER BY field, rows_count DESC, CASE WHEN raw_value IS NULL THEN 1 ELSE 0 END, raw_value, characters;
