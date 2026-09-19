-- =====================================================================
-- 02_clean.sql : raw text in, typed and standardised tables out
-- Dialect: PostgreSQL.
-- Every rule below answers a problem found in 01_profile_raw.sql.
-- =====================================================================
DROP SCHEMA IF EXISTS clean CASCADE;
CREATE SCHEMA clean;

-- ---------------------------------------------------------------------
-- 1. City lookup. The raw data spells 16 cities in dozens of ways: case,
--    stray spaces, abbreviations (KHI, LHR, ISB), "Cantt" suffixes, and a
--    common misspelling (Abbotabad). Keys are lower-cased and trimmed.
-- ---------------------------------------------------------------------
CREATE TABLE clean.city_map AS
SELECT * FROM (VALUES
    ('karachi', 'Karachi', 'Sindh', 1), ('khi', 'Karachi', 'Sindh', 1),
    ('karachi, sindh', 'Karachi', 'Sindh', 1),
    ('lahore', 'Lahore', 'Punjab', 1), ('lhr', 'Lahore', 'Punjab', 1),
    ('lahore cantt', 'Lahore', 'Punjab', 1),
    ('islamabad', 'Islamabad', 'Islamabad Capital Territory', 1),
    ('isb', 'Islamabad', 'Islamabad Capital Territory', 1),
    ('islamabad capital territory', 'Islamabad', 'Islamabad Capital Territory', 1),
    ('rawalpindi', 'Rawalpindi', 'Punjab', 1), ('pindi', 'Rawalpindi', 'Punjab', 1),
    ('rwp', 'Rawalpindi', 'Punjab', 1), ('rawalpindi cantt', 'Rawalpindi', 'Punjab', 1),
    ('faisalabad', 'Faisalabad', 'Punjab', 2), ('fsd', 'Faisalabad', 'Punjab', 2),
    ('multan', 'Multan', 'Punjab', 2),
    ('peshawar', 'Peshawar', 'Khyber Pakhtunkhwa', 2), ('pesh', 'Peshawar', 'Khyber Pakhtunkhwa', 2),
    ('hyderabad', 'Hyderabad', 'Sindh', 2), ('hyd', 'Hyderabad', 'Sindh', 2),
    ('hyderabad, sindh', 'Hyderabad', 'Sindh', 2),
    ('gujranwala', 'Gujranwala', 'Punjab', 2), ('grw', 'Gujranwala', 'Punjab', 2),
    ('sialkot', 'Sialkot', 'Punjab', 2), ('skt', 'Sialkot', 'Punjab', 2),
    ('quetta', 'Quetta', 'Balochistan', 3),
    ('bahawalpur', 'Bahawalpur', 'Punjab', 3), ('bwp', 'Bahawalpur', 'Punjab', 3),
    ('sukkur', 'Sukkur', 'Sindh', 3),
    ('abbottabad', 'Abbottabad', 'Khyber Pakhtunkhwa', 3),
    ('abbotabad', 'Abbottabad', 'Khyber Pakhtunkhwa', 3),
    ('sargodha', 'Sargodha', 'Punjab', 3),
    ('mardan', 'Mardan', 'Khyber Pakhtunkhwa', 3)
) AS t(raw_key, city, province, city_tier);

-- ---------------------------------------------------------------------
-- 2. Duplicate customer accounts. The same person registered twice with
--    the email typed differently (case, spaces). The earliest signup
--    becomes the canonical customer_id; every raw id maps to it.
--    QA test accounts are excluded here and everywhere downstream.
-- ---------------------------------------------------------------------
CREATE TABLE clean.customer_id_map AS
WITH ranked AS (
    SELECT customer_id,
           LOWER(TRIM(email)) AS email_key,
           ROW_NUMBER() OVER (
               PARTITION BY LOWER(TRIM(email))
               ORDER BY CAST(signup_date AS DATE) NULLS LAST, customer_id
           ) AS rn
    FROM raw.customers
    WHERE customer_id NOT LIKE 'TEST%'
)
SELECT r.customer_id AS raw_customer_id,
       k.customer_id AS customer_id
FROM ranked r
JOIN ranked k ON k.email_key = r.email_key AND k.rn = 1;

CREATE TABLE clean.customers AS
SELECT c.customer_id,
       LOWER(TRIM(c.email)) AS email,
       CAST(c.signup_date AS DATE) AS signup_date,
       m.city,
       m.province,
       m.city_tier,
       CASE
           WHEN LOWER(TRIM(c.acquisition_channel)) IN ('paid social', 'facebook ads', 'instagram ads') THEN 'Paid Social'
           WHEN LOWER(TRIM(c.acquisition_channel)) IN ('organic search', 'organic', 'google organic') THEN 'Organic Search'
           WHEN LOWER(TRIM(c.acquisition_channel)) IN ('app store', 'app_store') THEN 'App Store'
           ELSE TRIM(c.acquisition_channel)
       END AS acquisition_channel,
       c.device_type
FROM raw.customers c
JOIN clean.customer_id_map idm
  ON idm.raw_customer_id = c.customer_id
 AND idm.customer_id = c.customer_id            -- keep the canonical row only
LEFT JOIN clean.city_map m ON m.raw_key = LOWER(TRIM(c.city));

-- ---------------------------------------------------------------------
-- 3. Sellers and products. Category labels vary in case and in
--    "and" versus "&"; prices arrive as text.
-- ---------------------------------------------------------------------
CREATE TABLE clean.sellers AS
SELECT seller_id, seller_name, seller_city,
       CAST(joined_date AS DATE) AS joined_date,
       seller_type
FROM raw.sellers;

CREATE TABLE clean.products AS
SELECT product_id,
       product_name,
       CASE LOWER(TRIM(REPLACE(category, ' and ', ' & ')))
           WHEN 'fashion' THEN 'Fashion'
           WHEN 'footwear' THEN 'Footwear'
           WHEN 'electronics' THEN 'Electronics'
           WHEN 'mobile accessories' THEN 'Mobile Accessories'
           WHEN 'home & kitchen' THEN 'Home & Kitchen'
           WHEN 'beauty & personal care' THEN 'Beauty & Personal Care'
           WHEN 'grocery' THEN 'Grocery'
           WHEN 'baby & toys' THEN 'Baby & Toys'
       END AS category,
       subcategory,
       brand,
       seller_id,
       CAST(list_price AS NUMERIC(12, 2)) AS list_price,
       CAST(unit_cost AS NUMERIC(12, 2)) AS unit_cost
FROM raw.products;

-- ---------------------------------------------------------------------
-- 4. Orders. Problems handled, in order:
--    a. exact duplicate rows from an ingestion retry
--    b. two timestamp formats: the legacy system (before 2025-01-01)
--       wrote DD/MM/YYYY HH:MI, the new one writes ISO timestamps
--    c. two sets of status and payment labels, plus stray case and spaces
--    d. shipping fee stored as "Rs. 150" in the legacy system
--    e. blank shipping city: fall back to the customer's home city
--    f. delivery timestamps earlier than the order: set to NULL, flagged
--    g. QA test orders removed
-- ---------------------------------------------------------------------
CREATE TABLE clean.orders AS
WITH dedup AS (
    SELECT DISTINCT * FROM raw.orders
),
parsed AS (
    SELECT order_id,
           customer_id AS raw_customer_id,
           CASE WHEN order_datetime LIKE '__/__/____ __:__'
                THEN CAST(SUBSTRING(order_datetime, 7, 4) || '-' || SUBSTRING(order_datetime, 4, 2) || '-'
                          || SUBSTRING(order_datetime, 1, 2) || ' ' || SUBSTRING(order_datetime, 12, 5) || ':00' AS TIMESTAMP)
                ELSE CAST(order_datetime AS TIMESTAMP)
           END AS ordered_at,
           CASE WHEN delivered_at LIKE '__/__/____ __:__'
                THEN CAST(SUBSTRING(delivered_at, 7, 4) || '-' || SUBSTRING(delivered_at, 4, 2) || '-'
                          || SUBSTRING(delivered_at, 1, 2) || ' ' || SUBSTRING(delivered_at, 12, 5) || ':00' AS TIMESTAMP)
                ELSE CAST(NULLIF(TRIM(delivered_at), '') AS TIMESTAMP)
           END AS delivered_at_raw,
           CASE WHEN promised_delivery_date LIKE '__/__/____'
                THEN CAST(SUBSTRING(promised_delivery_date, 7, 4) || '-' || SUBSTRING(promised_delivery_date, 4, 2) || '-'
                          || SUBSTRING(promised_delivery_date, 1, 2) AS DATE)
                ELSE CAST(promised_delivery_date AS DATE)
           END AS promised_date,
           LOWER(TRIM(shipping_city)) AS city_key,
           LOWER(TRIM(payment_method)) AS pay_raw,
           LOWER(TRIM(order_status)) AS status_raw,
           NULLIF(NULLIF(UPPER(TRIM(promo_code)), ''), 'NONE') AS promo_code,
           courier,
           CAST(REGEXP_REPLACE(shipping_fee, '[^0-9]', '', 'g') AS INTEGER) AS shipping_fee
    FROM dedup
    WHERE customer_id NOT LIKE 'TEST%'
)
SELECT p.order_id,
       COALESCE(idm.customer_id, p.raw_customer_id) AS customer_id,
       p.ordered_at,
       CAST(p.ordered_at AS DATE) AS order_date,
       COALESCE(m.city, c.city) AS city,
       COALESCE(m.province, c.province) AS province,
       COALESCE(m.city_tier, c.city_tier) AS city_tier,
       CASE WHEN p.pay_raw IN ('cod', 'cash on delivery', 'cash_on_delivery') THEN 'Cash on Delivery'
            WHEN p.pay_raw IN ('card', 'cc') THEN 'Card'
            WHEN p.pay_raw IN ('jazzcash', 'easypaisa', 'wallet') THEN 'Mobile Wallet'
       END AS payment_method,
       CASE WHEN p.pay_raw IN ('cod', 'cash on delivery', 'cash_on_delivery') THEN 'COD' ELSE 'Prepaid' END AS payment_group,
       p.promo_code,
       p.courier,
       p.promised_date,
       CASE WHEN p.delivered_at_raw < p.ordered_at THEN NULL ELSE p.delivered_at_raw END AS delivered_at,
       COALESCE(p.delivered_at_raw < p.ordered_at, FALSE) AS delivered_before_ordered,
       CASE WHEN p.status_raw IN ('dlvd', 'delivered') THEN 'Delivered'
            WHEN p.status_raw IN ('cncl', 'cancelled', 'canceled') THEN 'Cancelled'
            WHEN p.status_raw IN ('rto', 'returned_to_origin') THEN 'Returned to Origin'
            WHEN p.status_raw IN ('shpd', 'shipped') THEN 'In Transit'
       END AS order_status,
       p.shipping_fee,
       p.ordered_at < TIMESTAMP '2025-01-01 00:00:00' AS from_legacy_system
FROM parsed p
LEFT JOIN clean.customer_id_map idm ON idm.raw_customer_id = p.raw_customer_id
LEFT JOIN clean.customers c ON c.customer_id = COALESCE(idm.customer_id, p.raw_customer_id)
LEFT JOIN clean.city_map m ON m.raw_key = p.city_key;

-- ---------------------------------------------------------------------
-- 5. Order items. Prices with an extra zero typed in (10x or 100x the
--    list price) are divided back and flagged; zero or negative
--    quantities are dropped; items of removed test orders are dropped.
-- ---------------------------------------------------------------------
CREATE TABLE clean.order_items AS
WITH typed AS (
    SELECT i.order_item_id,
           i.order_id,
           i.product_id,
           CAST(i.quantity AS INTEGER) AS quantity,
           CAST(i.unit_price AS NUMERIC(12, 2)) AS unit_price_raw,
           CAST(i.discount_pct AS INTEGER) AS discount_pct,
           p.list_price
    FROM raw.order_items i
    JOIN clean.products p ON p.product_id = i.product_id
)
SELECT order_item_id,
       order_id,
       product_id,
       quantity,
       discount_pct,
       CASE WHEN unit_price_raw > 50 * list_price THEN ROUND(unit_price_raw / 100, 2)
            WHEN unit_price_raw > 5 * list_price THEN ROUND(unit_price_raw / 10, 2)
            ELSE unit_price_raw
       END AS unit_price,
       unit_price_raw > 5 * list_price AS price_corrected
FROM typed
WHERE quantity > 0
  AND order_id IN (SELECT order_id FROM clean.orders);

-- ---------------------------------------------------------------------
-- 6. Returns. Orphan rows (item not found) are dropped.
-- ---------------------------------------------------------------------
CREATE TABLE clean.returns AS
SELECT r.return_id,
       r.order_item_id,
       i.order_id,
       TRIM(r.return_reason) AS return_reason,
       CAST(r.return_requested_date AS DATE) AS return_requested_date,
       CAST(r.refund_amount AS NUMERIC(12, 2)) AS refund_amount
FROM raw.returns r
JOIN clean.order_items i ON i.order_item_id = r.order_item_id;

-- ---------------------------------------------------------------------
-- 7. Checkout sessions from the one-page checkout experiment.
--    Duplicate rows removed, group labels standardised, and sessions
--    shorter than 3 seconds flagged as bots rather than deleted, so the
--    A/B analysis can show their effect.
-- ---------------------------------------------------------------------
CREATE TABLE clean.checkout_sessions AS
SELECT DISTINCT
       session_id,
       customer_id,
       CAST(session_start AS TIMESTAMP) AS session_start,
       device_type,
       traffic_source,
       LOWER(TRIM(experiment_group)) AS experiment_group,
       CAST(session_duration_sec AS INTEGER) AS session_duration_sec,
       CAST(session_duration_sec AS INTEGER) < 3 AS is_bot,
       CAST(completed_order AS INTEGER) AS completed_order,
       CAST(order_value AS NUMERIC(12, 2)) AS order_value
FROM raw.checkout_sessions;
