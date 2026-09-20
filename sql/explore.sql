-- =====================================================================
-- explore.sql : a guided tour of the Kaarobar database, one query at a time
--
-- How to use it: put the cursor anywhere in a numbered block, select the
-- whole block, and press Ctrl+Shift+E. Only the selected text runs, and the
-- result opens in a grid below the editor.
--
-- Nothing here changes anything. Every query is a SELECT.
-- =====================================================================


-- 1. What is inside the database?
-- Three layers: raw is exactly what the CSVs gave us, clean is the fixed
-- version, mart is what analysis reads. Anything starting v_ is a view,
-- which is a saved query rather than a stored table.
SELECT TABLE_SCHEMA AS layer, TABLE_NAME AS object_name, TABLE_TYPE AS kind
FROM INFORMATION_SCHEMA.TABLES
ORDER BY CASE TABLE_SCHEMA WHEN 'raw' THEN 1 WHEN 'clean' THEN 2 ELSE 3 END, TABLE_NAME;


-- 2. The mess, before anything is fixed.
-- Look at order_datetime (two different formats), shipping_fee ('Rs. 150' as
-- text), shipping_city (spelled several ways), and order_status ('DLVD').
SELECT TOP 20 order_id, order_datetime, shipping_city, payment_method, order_status, shipping_fee
FROM raw.orders
ORDER BY order_id;


-- 3. How bad is the city problem?
-- SQL Server treats 'lahore', 'Lahore' and 'Lahore ' as the same text, so a
-- plain COUNT(DISTINCT ...) hides the problem. COLLATE Latin1_General_BIN2
-- compares byte for byte, and adding '|' keeps a trailing space visible.
SELECT COUNT(DISTINCT shipping_city) AS what_sql_server_sees_by_default,
       COUNT(DISTINCT (shipping_city + '|') COLLATE Latin1_General_BIN2) AS real_spellings
FROM raw.orders;


-- 4. The fix: a lookup table from every spelling to one real city.
-- This is built in 02_clean.sql. Every messy spelling points at one city,
-- province and tier, so later queries never have to know about the mess.
SELECT TOP 25 raw_key, city, province, city_tier
FROM clean.city_map
ORDER BY city, raw_key;


-- 5. One order, before and after cleaning.
-- Picks an order stored in the old DD/MM/YYYY format and shows both versions.
DECLARE @order_id nvarchar(20) =
    (SELECT TOP 1 order_id FROM raw.orders
     WHERE order_datetime LIKE '__/__/____ __:__' ORDER BY order_id);

SELECT 'raw' AS layer,
       CAST(order_datetime AS nvarchar(30)) AS ordered,
       shipping_city AS city,
       CAST(shipping_fee AS nvarchar(20)) AS shipping_fee,
       order_status
FROM raw.orders WHERE order_id = @order_id
UNION ALL
SELECT 'clean',
       CONVERT(nvarchar(30), ordered_at, 120),
       city,
       CAST(shipping_fee AS nvarchar(20)),
       order_status
FROM clean.orders WHERE order_id = @order_id;


-- 6. What did cleaning throw away?
-- The gap between the two columns is duplicates, QA test accounts, merged
-- customer accounts and broken rows. 05_quality_checks.sql proves each one.
SELECT 'orders' AS table_name, (SELECT COUNT(*) FROM raw.orders) AS raw_rows,
       (SELECT COUNT(*) FROM clean.orders) AS clean_rows
UNION ALL
SELECT 'customers', (SELECT COUNT(*) FROM raw.customers), (SELECT COUNT(*) FROM clean.customers)
UNION ALL
SELECT 'order_items', (SELECT COUNT(*) FROM raw.order_items), (SELECT COUNT(*) FROM clean.order_items)
UNION ALL
SELECT 'returns', (SELECT COUNT(*) FROM raw.returns), (SELECT COUNT(*) FROM clean.returns)
UNION ALL
SELECT 'checkout_sessions', (SELECT COUNT(*) FROM raw.checkout_sessions),
       (SELECT COUNT(*) FROM clean.checkout_sessions);


-- 7. One customer's order history in the fact table.
-- customer_order_seq comes from ROW_NUMBER(): it numbers each customer's
-- orders in time order, which is what makes first-order and repeat analysis
-- possible. is_rto means the parcel came back refused.
SELECT TOP 20 customer_id, customer_order_seq, order_date, city, payment_group,
       order_status, gmv, net_revenue, delivery_days, is_late, is_rto
FROM mart.fact_orders
WHERE customer_id = (SELECT TOP 1 customer_id FROM mart.dim_customers
                     WHERE orders >= 5 ORDER BY customer_id)
ORDER BY customer_order_seq;


-- 8. The headline numbers, from a view.
-- A view is just a saved SELECT. Reading from it runs the query fresh.
SELECT * FROM mart.v_headline_kpis;


-- 9. Read the SQL behind any view.
-- Change the name to any view from step 1 and run it. Click the cell in the
-- grid to read the whole thing. This is how you check what a number means.
SELECT OBJECT_DEFINITION(OBJECT_ID('mart.v_headline_kpis')) AS view_sql;


-- 10. A real finding: refused parcels (RTO) by payment type and city tier.
-- Cash on delivery is refused roughly ten times as often as prepaid. Tier 3
-- cities are worse again. This is the single most useful table in the project.
SELECT * FROM mart.v_rto_by_tier ORDER BY city_tier, payment_group;


-- 11. Courier quality, which is the other half of the same story.
SELECT * FROM mart.v_courier_scorecard ORDER BY courier, city_tier;


-- 12. Cohort retention: of the customers who first ordered in a given month,
-- how many were still ordering N months later.
SELECT cohort_month, months_since_first, cohort_size, active_customers, retention_pct
FROM mart.v_cohort_retention
WHERE cohort_month = '2024-01-01'
ORDER BY months_since_first;


-- 13. Sellers returning more than their category normally does.
-- z_score says how far above the category average a seller sits, counted in
-- standard deviations. flagged = 1 is the shortlist worth investigating.
SELECT * FROM mart.v_seller_returns WHERE flagged = 1 ORDER BY z_score DESC;


-- =====================================================================
-- Your turn. Write these yourself, then check against a view in step 1.
--   a) Net revenue by month. Hint: GROUP BY order_month on mart.fact_orders.
--      Compare with mart.v_monthly_kpis.
--   b) The five cities with the worst late delivery rate, counting only
--      cities with at least 500 delivered orders. Hint: AVG over a CASE, and
--      HAVING COUNT(*) >= 500.
--   c) Do customers whose first order arrived late come back less often?
--      Hint: mart.dim_customers has first_order_late and repeat_within_90d.
--      Compare with mart.v_first_order_experience.
-- =====================================================================
