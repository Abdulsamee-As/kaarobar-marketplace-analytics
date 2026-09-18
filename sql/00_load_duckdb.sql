-- =====================================================================
-- 00_load_duckdb.sql : load the raw CSV extracts into DuckDB
-- Every column is loaded as text, exactly as delivered. Typing happens in
-- 02_clean.sql, where bad values can be caught instead of crashing the load.
-- Run from the project root (python src/run_pipeline.py does this for you).
-- =====================================================================
DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

CREATE TABLE raw.customers         AS SELECT * FROM read_csv('data/raw/customers.csv',         header = true, all_varchar = true);
CREATE TABLE raw.sellers           AS SELECT * FROM read_csv('data/raw/sellers.csv',           header = true, all_varchar = true);
CREATE TABLE raw.products          AS SELECT * FROM read_csv('data/raw/products.csv',          header = true, all_varchar = true);
CREATE TABLE raw.orders            AS SELECT * FROM read_csv('data/raw/orders.csv',            header = true, all_varchar = true);
CREATE TABLE raw.order_items       AS SELECT * FROM read_csv('data/raw/order_items.csv',       header = true, all_varchar = true);
CREATE TABLE raw.returns           AS SELECT * FROM read_csv('data/raw/returns.csv',           header = true, all_varchar = true);
CREATE TABLE raw.checkout_sessions AS SELECT * FROM read_csv('data/raw/checkout_sessions.csv', header = true, all_varchar = true);
