-- =====================================================================
-- 00_load_postgres.sql : load the raw CSV extracts into PostgreSQL
-- Every column is TEXT, exactly as delivered. Typing happens in 02_clean.sql.
-- Run with psql from the project root:
--   psql -d kaarobar -f sql/00_load_postgres.sql
-- then run 01 to 05 in order with psql -f.
-- =====================================================================
DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

CREATE TABLE raw.customers (
    customer_id TEXT, email TEXT, signup_date TEXT, city TEXT,
    acquisition_channel TEXT, device_type TEXT
);
CREATE TABLE raw.sellers (
    seller_id TEXT, seller_name TEXT, seller_city TEXT, joined_date TEXT, seller_type TEXT
);
CREATE TABLE raw.products (
    product_id TEXT, product_name TEXT, category TEXT, subcategory TEXT,
    brand TEXT, seller_id TEXT, list_price TEXT, unit_cost TEXT
);
CREATE TABLE raw.orders (
    order_id TEXT, customer_id TEXT, order_datetime TEXT, shipping_city TEXT,
    payment_method TEXT, promo_code TEXT, courier TEXT, promised_delivery_date TEXT,
    delivered_at TEXT, order_status TEXT, shipping_fee TEXT
);
CREATE TABLE raw.order_items (
    order_item_id TEXT, order_id TEXT, product_id TEXT, quantity TEXT,
    unit_price TEXT, discount_pct TEXT
);
CREATE TABLE raw.returns (
    return_id TEXT, order_item_id TEXT, order_id TEXT, return_reason TEXT,
    return_requested_date TEXT, refund_amount TEXT
);
CREATE TABLE raw.checkout_sessions (
    session_id TEXT, customer_id TEXT, session_start TEXT, device_type TEXT,
    traffic_source TEXT, experiment_group TEXT, session_duration_sec TEXT,
    completed_order TEXT, order_value TEXT
);

\copy raw.customers         FROM 'data/raw/customers.csv'         WITH (FORMAT csv, HEADER true)
\copy raw.sellers           FROM 'data/raw/sellers.csv'           WITH (FORMAT csv, HEADER true)
\copy raw.products          FROM 'data/raw/products.csv'          WITH (FORMAT csv, HEADER true)
\copy raw.orders            FROM 'data/raw/orders.csv'            WITH (FORMAT csv, HEADER true)
\copy raw.order_items       FROM 'data/raw/order_items.csv'       WITH (FORMAT csv, HEADER true)
\copy raw.returns           FROM 'data/raw/returns.csv'           WITH (FORMAT csv, HEADER true)
\copy raw.checkout_sessions FROM 'data/raw/checkout_sessions.csv' WITH (FORMAT csv, HEADER true)
