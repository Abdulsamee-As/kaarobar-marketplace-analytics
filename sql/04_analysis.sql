-- =====================================================================
-- 04_analysis.sql : the business questions, one view each
-- Money is in PKR. Net revenue = delivered GMV minus refunds.
-- Rates are percentages rounded to two decimals.
-- Dialect: T-SQL (SQL Server 2017 or later).
-- =====================================================================

-- Headline numbers for the whole period
CREATE OR ALTER VIEW mart.v_headline_kpis AS
SELECT COUNT(*) AS orders,
       COUNT(DISTINCT customer_id) AS ordering_customers,
       SUM(gmv) AS gmv,
       SUM(net_revenue) AS net_revenue,
       CAST(ROUND(SUM(gmv) / COUNT(*), 0) AS decimal(18, 0)) AS avg_order_value,
       CAST(ROUND(100.0 * SUM(CASE WHEN payment_group = 'COD' THEN 1 ELSE 0 END) / COUNT(*), 2) AS decimal(18, 2)) AS cod_share_pct,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN order_status IN ('Delivered', 'Returned to Origin') THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS rto_rate_pct,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_late = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN is_late IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS late_delivery_pct
FROM mart.fact_orders;
GO

-- Q1. How fast is the business growing?
CREATE OR ALTER VIEW mart.v_monthly_kpis AS
WITH m AS (
    SELECT order_month,
           COUNT(*) AS orders,
           SUM(CASE WHEN order_status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders,
           SUM(gmv) AS gmv,
           SUM(net_revenue) AS net_revenue,
           SUM(CASE WHEN customer_order_seq = 1 THEN 1 ELSE 0 END) AS new_customers,
           SUM(CASE WHEN payment_group = 'COD' THEN 1 ELSE 0 END) AS cod_orders
    FROM mart.fact_orders
    GROUP BY order_month
)
SELECT order_month,
       orders,
       delivered_orders,
       gmv,
       net_revenue,
       new_customers,
       CAST(ROUND(gmv / orders, 0) AS decimal(18, 0)) AS avg_order_value,
       CAST(ROUND(100.0 * cod_orders / orders, 2) AS decimal(18, 2)) AS cod_share_pct,
       CAST(ROUND(100.0 * (net_revenue - LAG(net_revenue) OVER (ORDER BY order_month))
            / NULLIF(LAG(net_revenue) OVER (ORDER BY order_month), 0), 2) AS decimal(18, 2)) AS net_revenue_mom_pct
FROM m;
GO

-- Q2. When do people buy? Daily orders, for the seasonality chart.
CREATE OR ALTER VIEW mart.v_daily_orders AS
SELECT order_date,
       COUNT(*) AS orders,
       SUM(gmv) AS gmv
FROM mart.fact_orders
GROUP BY order_date;
GO

-- Q3. How are customers paying, and how is that changing?
CREATE OR ALTER VIEW mart.v_payment_mix AS
SELECT order_month,
       payment_method,
       COUNT(*) AS orders,
       CAST(ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY order_month), 2) AS decimal(18, 2)) AS share_pct
FROM mart.fact_orders
GROUP BY order_month, payment_method;
GO

-- Q4. Who refuses parcels at the door? Return-to-origin (RTO) rate among
--     shipped orders, by payment type, customer type, and order value.
CREATE OR ALTER VIEW mart.v_rto_drivers AS
SELECT payment_group,
       CASE WHEN customer_order_seq = 1 THEN 'First order' ELSE 'Repeat order' END AS customer_type,
       CASE WHEN gmv > 15000 THEN 'Above PKR 15,000' ELSE 'PKR 15,000 or less' END AS order_value_band,
       COUNT(*) AS shipped_orders,
       SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END) AS rto_orders,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS decimal(18, 2)) AS rto_rate_pct
FROM mart.fact_orders
WHERE order_status IN ('Delivered', 'Returned to Origin')
GROUP BY payment_group,
         CASE WHEN customer_order_seq = 1 THEN 'First order' ELSE 'Repeat order' END,
         CASE WHEN gmv > 15000 THEN 'Above PKR 15,000' ELSE 'PKR 15,000 or less' END;
GO

-- Q4b. RTO by city tier and payment type
CREATE OR ALTER VIEW mart.v_rto_by_tier AS
SELECT city_tier,
       payment_group,
       COUNT(*) AS shipped_orders,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS decimal(18, 2)) AS rto_rate_pct
FROM mart.fact_orders
WHERE order_status IN ('Delivered', 'Returned to Origin')
GROUP BY city_tier, payment_group;
GO

-- Q4c. What do refused parcels cost? Assumption: PKR 180 courier fee each
--      way plus PKR 60 packaging and handling, so PKR 420 per RTO order.
CREATE OR ALTER VIEW mart.v_rto_cost AS
SELECT YEAR(order_date) AS order_year,
       payment_group,
       SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END) AS rto_orders,
       SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END) * 420 AS est_rto_cost_pkr,
       SUM(CASE WHEN is_rto = 1 THEN gmv ELSE 0 END) AS refused_gmv_pkr
FROM mart.fact_orders
GROUP BY YEAR(order_date), payment_group;
GO

-- Q5. Which courier delivers on time, and where?
CREATE OR ALTER VIEW mart.v_courier_scorecard AS
SELECT courier,
       city_tier,
       COUNT(*) AS orders,
       CAST(ROUND(AVG(CAST(delivery_days AS decimal(10, 4))), 2) AS decimal(18, 2)) AS avg_delivery_days,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_late = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN is_late IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS late_rate_pct,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN order_status IN ('Delivered', 'Returned to Origin') THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS rto_rate_pct
FROM mart.fact_orders
GROUP BY courier, city_tier;
GO

-- Q6. Did moving volume to the cheapest courier in mid-2025 hurt delivery?
CREATE OR ALTER VIEW mart.v_delivery_monthly AS
SELECT order_month,
       CAST(ROUND(100.0 * SUM(CASE WHEN courier = 'RapidRoute' THEN 1 ELSE 0 END) / COUNT(*), 2) AS decimal(18, 2)) AS rapidroute_share_pct,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_late = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN is_late IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS late_rate_pct,
       CAST(ROUND(100.0 * SUM(CASE WHEN is_rto = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN order_status IN ('Delivered', 'Returned to Origin') THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS rto_rate_pct
FROM mart.fact_orders
GROUP BY order_month;
GO

-- Q7. Does the first order decide whether a customer comes back?
CREATE OR ALTER VIEW mart.v_first_order_experience AS
WITH labelled AS (
    SELECT customer_id,
           repeat_within_90d,
           CASE WHEN first_order_status = 'Returned to Origin' THEN 'Refused at door (RTO)'
                WHEN first_order_status = 'Cancelled' THEN 'Cancelled'
                WHEN first_order_status = 'Delivered' AND first_order_late = 1 THEN 'Delivered late'
                WHEN first_order_status = 'Delivered' AND first_order_late = 0 THEN 'Delivered on time'
           END AS first_order_experience
    FROM mart.dim_customers
    WHERE repeat_within_90d IS NOT NULL
)
SELECT first_order_experience,
       COUNT(*) AS customers,
       CAST(ROUND(100.0 * SUM(CASE WHEN repeat_within_90d = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS decimal(18, 2)) AS repeat_90d_pct
FROM labelled
WHERE first_order_experience IS NOT NULL
GROUP BY first_order_experience;
GO

-- Q8. Monthly cohort retention: share of each first-order cohort that
--     orders again N months later.
CREATE OR ALTER VIEW mart.v_cohort_retention AS
WITH activity AS (
    SELECT DISTINCT
           d.customer_id,
           d.cohort_month,
           DATEDIFF(month, d.cohort_month, f.order_month) AS months_since_first
    FROM mart.dim_customers d
    JOIN mart.fact_orders f ON f.customer_id = d.customer_id
),
sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM mart.dim_customers
    WHERE cohort_month IS NOT NULL
    GROUP BY cohort_month
)
SELECT a.cohort_month,
       a.months_since_first,
       s.cohort_size,
       COUNT(*) AS active_customers,
       CAST(ROUND(100.0 * COUNT(*) / s.cohort_size, 2) AS decimal(18, 2)) AS retention_pct
FROM activity a
JOIN sizes s ON s.cohort_month = a.cohort_month
WHERE a.months_since_first BETWEEN 0 AND 12
GROUP BY a.cohort_month, a.months_since_first, s.cohort_size;
GO

-- Q9. Are customers won in mega sales worth as much?
CREATE OR ALTER VIEW mart.v_acquisition_quality AS
SELECT CASE WHEN acquired_in_mega_sale = 1 THEN 'First order used a mega-sale code'
            ELSE 'First order at any other time' END AS acquisition,
       COUNT(*) AS customers,
       CAST(ROUND(100.0 * SUM(CASE WHEN repeat_within_90d = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN repeat_within_90d IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS repeat_90d_pct,
       CAST(ROUND(AVG(CAST(orders AS decimal(10, 4))), 2) AS decimal(18, 2)) AS avg_orders,
       CAST(ROUND(AVG(net_revenue), 0) AS decimal(18, 0)) AS avg_net_revenue
FROM mart.dim_customers
WHERE first_order_date IS NOT NULL
GROUP BY CASE WHEN acquired_in_mega_sale = 1 THEN 'First order used a mega-sale code'
              ELSE 'First order at any other time' END;
GO

-- Q9b. Acquisition channel quality
CREATE OR ALTER VIEW mart.v_channel_quality AS
SELECT acquisition_channel,
       COUNT(*) AS customers,
       CAST(ROUND(100.0 * SUM(CASE WHEN repeat_within_90d = 1 THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN repeat_within_90d IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS decimal(18, 2)) AS repeat_90d_pct,
       CAST(ROUND(AVG(net_revenue), 0) AS decimal(18, 0)) AS avg_net_revenue
FROM mart.dim_customers
WHERE first_order_date IS NOT NULL
GROUP BY acquisition_channel;
GO

-- Q10. What comes back, and why?
CREATE OR ALTER VIEW mart.v_returns_by_category AS
WITH sold AS (
    SELECT p.category, COUNT(*) AS items_delivered
    FROM clean.order_items i
    JOIN clean.products p ON p.product_id = i.product_id
    JOIN mart.fact_orders f ON f.order_id = i.order_id
    WHERE f.order_status = 'Delivered'
    GROUP BY p.category
),
ret AS (
    SELECT p.category,
           COUNT(*) AS items_returned,
           SUM(CASE WHEN r.return_reason = 'Size or fit issue' THEN 1 ELSE 0 END) AS size_or_fit,
           SUM(CASE WHEN r.return_reason = 'Not as described' THEN 1 ELSE 0 END) AS not_as_described,
           SUM(CASE WHEN r.return_reason = 'Defective or damaged' THEN 1 ELSE 0 END) AS defective_or_damaged,
           SUM(CASE WHEN r.return_reason = 'Arrived too late' THEN 1 ELSE 0 END) AS arrived_too_late,
           SUM(CASE WHEN r.return_reason = 'Changed mind' THEN 1 ELSE 0 END) AS changed_mind,
           SUM(r.refund_amount) AS refunded_value
    FROM clean.returns r
    JOIN clean.order_items i ON i.order_item_id = r.order_item_id
    JOIN clean.products p ON p.product_id = i.product_id
    GROUP BY p.category
)
SELECT s.category,
       s.items_delivered,
       COALESCE(r.items_returned, 0) AS items_returned,
       CAST(ROUND(100.0 * COALESCE(r.items_returned, 0) / s.items_delivered, 2) AS decimal(18, 2)) AS return_rate_pct,
       r.size_or_fit,
       r.not_as_described,
       r.defective_or_damaged,
       r.arrived_too_late,
       r.changed_mind,
       r.refunded_value
FROM sold s
LEFT JOIN ret r ON r.category = s.category;
GO

-- Q11. Which sellers ship items that do not match their listing?
--      Flag: at least 50 items delivered and a return rate more than three
--      standard errors above the category average (a one-sided binomial
--      z-test), so small sellers are not flagged by chance.
CREATE OR ALTER VIEW mart.v_seller_returns AS
WITH item_level AS (
    SELECT p.seller_id,
           p.category,
           CASE WHEN r.return_id IS NOT NULL THEN 1 ELSE 0 END AS returned,
           CASE WHEN r.return_reason = 'Not as described' THEN 1 ELSE 0 END AS not_as_described
    FROM clean.order_items i
    JOIN clean.products p ON p.product_id = i.product_id
    JOIN mart.fact_orders f ON f.order_id = i.order_id AND f.order_status = 'Delivered'
    LEFT JOIN clean.returns r ON r.order_item_id = i.order_item_id
),
by_seller AS (
    SELECT seller_id,
           category,
           COUNT(*) AS items_delivered,
           SUM(returned) AS items_returned,
           SUM(not_as_described) AS not_as_described_returns
    FROM item_level
    GROUP BY seller_id, category
),
by_category AS (
    SELECT category,
           1.0 * SUM(items_returned) / SUM(items_delivered) AS category_return_rate
    FROM by_seller
    GROUP BY category
)
SELECT s.seller_id,
       se.seller_name,
       s.category,
       s.items_delivered,
       s.items_returned,
       s.not_as_described_returns,
       CAST(ROUND(100.0 * s.items_returned / s.items_delivered, 2) AS decimal(18, 2)) AS return_rate_pct,
       CAST(ROUND(100.0 * c.category_return_rate, 2) AS decimal(18, 2)) AS category_return_rate_pct,
       CAST(ROUND((1.0 * s.items_returned / s.items_delivered - c.category_return_rate)
            / SQRT(c.category_return_rate * (1 - c.category_return_rate) / s.items_delivered), 2) AS decimal(18, 2)) AS z_score,
       CAST(CASE WHEN s.items_delivered >= 50
                  AND (1.0 * s.items_returned / s.items_delivered - c.category_return_rate)
                      / SQRT(c.category_return_rate * (1 - c.category_return_rate) / s.items_delivered) > 3
                 THEN 1 ELSE 0 END AS bit) AS flagged
FROM by_seller s
JOIN by_category c ON c.category = s.category
JOIN clean.sellers se ON se.seller_id = s.seller_id;
GO

-- Q12. RFM segmentation of customers with at least one delivered order.
--      Recency, frequency, and monetary value each scored 1 to 5.
--      customer_id breaks ties so the scores are identical on every run.
CREATE OR ALTER VIEW mart.v_rfm AS
WITH base AS (
    SELECT customer_id,
           DATEDIFF(day, MAX(order_date), CAST('2026-06-30' AS date)) AS recency_days,
           SUM(CASE WHEN order_status = 'Delivered' THEN 1 ELSE 0 END) AS frequency,
           SUM(net_revenue) AS monetary
    FROM mart.fact_orders
    GROUP BY customer_id
    HAVING SUM(CASE WHEN order_status = 'Delivered' THEN 1 ELSE 0 END) > 0
),
scored AS (
    SELECT customer_id, recency_days, frequency, monetary,
           NTILE(5) OVER (ORDER BY recency_days DESC, customer_id) AS r_score,
           NTILE(5) OVER (ORDER BY frequency, monetary, customer_id) AS f_score,
           NTILE(5) OVER (ORDER BY monetary, customer_id) AS m_score
    FROM base
)
SELECT customer_id, recency_days, frequency, monetary, r_score, f_score, m_score,
       CASE WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'New or promising'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At risk'
            WHEN r_score <= 2 AND f_score <= 2 THEN 'Lost'
            ELSE 'Needs attention'
       END AS segment
FROM scored;
GO

CREATE OR ALTER VIEW mart.v_rfm_summary AS
SELECT segment,
       COUNT(*) AS customers,
       CAST(ROUND(AVG(CAST(recency_days AS decimal(10, 4))), 0) AS decimal(18, 0)) AS avg_recency_days,
       CAST(ROUND(AVG(CAST(frequency AS decimal(10, 4))), 2) AS decimal(18, 2)) AS avg_delivered_orders,
       SUM(monetary) AS net_revenue,
       CAST(ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS decimal(18, 2)) AS revenue_share_pct
FROM mart.v_rfm
GROUP BY segment;
GO

-- Q13. The one-page checkout A/B test: sessions and orders by group,
--      device, and bot flag. Significance tests run in src/ab_test.py.
CREATE OR ALTER VIEW mart.v_ab_test AS
SELECT experiment_group,
       device_type,
       is_bot,
       COUNT(*) AS sessions,
       SUM(completed_order) AS orders,
       SUM(order_value) AS revenue
FROM clean.checkout_sessions
GROUP BY experiment_group, device_type, is_bot;
GO

-- Q14. Where is growth coming from? Orders, COD share, and RTO rate by
--      city tier, per half-year.
CREATE OR ALTER VIEW mart.v_city_tier_growth AS
SELECT YEAR(order_date) AS order_year,
       CASE WHEN MONTH(order_date) <= 6 THEN 1 ELSE 2 END AS half,
       city_tier,
       COUNT(*) AS orders,
       CAST(ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (
           PARTITION BY YEAR(order_date), CASE WHEN MONTH(order_date) <= 6 THEN 1 ELSE 2 END), 2) AS decimal(18, 2)) AS order_share_pct,
       CAST(ROUND(100.0 * SUM(CASE WHEN payment_group = 'COD' THEN 1 ELSE 0 END) / COUNT(*), 2) AS decimal(18, 2)) AS cod_share_pct
FROM mart.fact_orders
WHERE city_tier IS NOT NULL
GROUP BY YEAR(order_date), CASE WHEN MONTH(order_date) <= 6 THEN 1 ELSE 2 END, city_tier;
GO
