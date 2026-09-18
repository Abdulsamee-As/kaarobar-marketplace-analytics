-- =====================================================================
-- 03_model.sql : analysis-ready tables
-- fact_orders   one row per order: money, delivery, and order sequence
-- dim_customers one row per customer: cohort, first-order experience, value
-- Dialect: PostgreSQL. Also runs unchanged in DuckDB.
-- =====================================================================
DROP SCHEMA IF EXISTS mart CASCADE;
CREATE SCHEMA mart;

CREATE TABLE mart.fact_orders AS
WITH items AS (
    SELECT i.order_id,
           COUNT(*) AS items_count,
           SUM(i.quantity) AS units,
           SUM(i.quantity * i.unit_price) AS gmv,
           SUM(i.quantity * p.unit_cost) AS cogs,
           SUM(i.quantity * p.list_price) AS list_value
    FROM clean.order_items i
    JOIN clean.products p ON p.product_id = i.product_id
    GROUP BY i.order_id
),
rets AS (
    SELECT order_id,
           COUNT(*) AS returned_items,
           SUM(refund_amount) AS refunded_value
    FROM clean.returns
    GROUP BY order_id
)
SELECT o.order_id,
       o.customer_id,
       o.ordered_at,
       o.order_date,
       CAST(DATE_TRUNC('month', o.order_date) AS DATE) AS order_month,
       o.city,
       o.province,
       o.city_tier,
       o.payment_method,
       o.payment_group,
       o.promo_code,
       o.courier,
       o.order_status,
       o.promised_date,
       o.delivered_at,
       o.shipping_fee,
       o.from_legacy_system,
       it.items_count,
       it.units,
       it.gmv,
       it.cogs,
       it.list_value - it.gmv AS discount_value,
       COALESCE(r.returned_items, 0) AS returned_items,
       COALESCE(r.refunded_value, 0) AS refunded_value,
       -- net revenue: what the business keeps from delivered orders after refunds
       CASE WHEN o.order_status = 'Delivered' THEN it.gmv - COALESCE(r.refunded_value, 0) ELSE 0 END AS net_revenue,
       o.promised_date - o.order_date AS promised_days,
       CASE WHEN o.order_status = 'Delivered' AND o.delivered_at IS NOT NULL
            THEN CAST(o.delivered_at AS DATE) - o.order_date END AS delivery_days,
       CASE WHEN o.order_status = 'Delivered' AND o.delivered_at IS NOT NULL
            THEN CAST(o.delivered_at AS DATE) > o.promised_date END AS is_late,
       o.order_status = 'Returned to Origin' AS is_rto,
       ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY o.ordered_at, o.order_id) AS customer_order_seq
FROM clean.orders o
JOIN items it ON it.order_id = o.order_id
LEFT JOIN rets r ON r.order_id = o.order_id;

CREATE TABLE mart.dim_customers AS
WITH firsts AS (
    SELECT customer_id,
           order_date AS first_order_date,
           order_month AS cohort_month,
           promo_code AS first_promo_code,
           order_status AS first_order_status,
           payment_group AS first_payment_group,
           is_late AS first_order_late
    FROM mart.fact_orders
    WHERE customer_order_seq = 1
),
seconds AS (
    SELECT customer_id, order_date AS second_order_date
    FROM mart.fact_orders
    WHERE customer_order_seq = 2
),
totals AS (
    SELECT customer_id,
           COUNT(*) AS orders,
           COUNT(*) FILTER (WHERE order_status = 'Delivered') AS delivered_orders,
           SUM(net_revenue) AS net_revenue,
           MAX(order_date) AS last_order_date
    FROM mart.fact_orders
    GROUP BY customer_id
)
SELECT c.customer_id,
       c.signup_date,
       c.city,
       c.province,
       c.city_tier,
       c.acquisition_channel,
       c.device_type,
       f.first_order_date,
       f.cohort_month,
       f.first_promo_code,
       COALESCE(f.first_promo_code IN ('MEGA1111', 'WHITEFRI', 'SALE1212', 'AZADI14'), FALSE) AS acquired_in_mega_sale,
       f.first_order_status,
       f.first_payment_group,
       f.first_order_late,
       s.second_order_date,
       -- a 90-day repeat can only be judged when the first order is at least
       -- 90 days before the data extract (2026-06-30)
       CASE WHEN DATE '2026-06-30' - f.first_order_date >= 90
            THEN COALESCE(s.second_order_date - f.first_order_date <= 90, FALSE)
       END AS repeat_within_90d,
       COALESCE(t.orders, 0) AS orders,
       COALESCE(t.delivered_orders, 0) AS delivered_orders,
       COALESCE(t.net_revenue, 0) AS net_revenue,
       t.last_order_date
FROM clean.customers c
LEFT JOIN firsts f ON f.customer_id = c.customer_id
LEFT JOIN seconds s ON s.customer_id = c.customer_id
LEFT JOIN totals t ON t.customer_id = c.customer_id;
