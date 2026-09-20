IF SCHEMA_ID('clean') IS NULL EXEC('CREATE SCHEMA clean');
GO

DROP TABLE IF EXISTS clean.city_map;
GO
SELECT raw_key, city, province, city_tier
INTO clean.city_map
FROM (VALUES
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
GO

DROP TABLE IF EXISTS clean.customer_id_map;
GO
WITH ranked AS (
    SELECT customer_id,
           LOWER(TRIM(email)) AS email_key,
           ROW_NUMBER() OVER (
               PARTITION BY LOWER(TRIM(email))
               ORDER BY CASE WHEN TRY_CONVERT(date, signup_date) IS NULL THEN 1 ELSE 0 END,
                        TRY_CONVERT(date, signup_date),
                        customer_id
           ) AS rn
    FROM raw.customers
    WHERE customer_id NOT LIKE 'TEST%'
)
SELECT r.customer_id AS raw_customer_id,
       k.customer_id AS customer_id
INTO clean.customer_id_map
FROM ranked r
JOIN ranked k ON k.email_key = r.email_key AND k.rn = 1;
GO

DROP TABLE IF EXISTS clean.customers;
GO
SELECT c.customer_id,
       LOWER(TRIM(c.email)) AS email,
       TRY_CONVERT(date, c.signup_date) AS signup_date,
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
INTO clean.customers
FROM raw.customers c
JOIN clean.customer_id_map idm
  ON idm.raw_customer_id = c.customer_id
 AND idm.customer_id = c.customer_id
LEFT JOIN clean.city_map m ON m.raw_key = LOWER(TRIM(c.city));
GO

DROP TABLE IF EXISTS clean.sellers;
GO
SELECT seller_id,
       seller_name,
       seller_city,
       TRY_CONVERT(date, joined_date) AS joined_date,
       seller_type
INTO clean.sellers
FROM raw.sellers;
GO

DROP TABLE IF EXISTS clean.products;
GO
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
       TRY_CONVERT(decimal(14, 2), list_price) AS list_price,
       TRY_CONVERT(decimal(14, 2), unit_cost) AS unit_cost
INTO clean.products
FROM raw.products;
GO

DROP TABLE IF EXISTS clean.orders;
GO
WITH dedup AS (
    SELECT DISTINCT * FROM raw.orders
),
parsed AS (
    SELECT order_id,
           customer_id AS raw_customer_id,
           CASE WHEN order_datetime LIKE '__/__/____ __:__'
                THEN TRY_CONVERT(datetime2(0), order_datetime, 103)
                ELSE TRY_CONVERT(datetime2(0), order_datetime, 120)
           END AS ordered_at,
           CASE WHEN delivered_at LIKE '__/__/____ __:__'
                THEN TRY_CONVERT(datetime2(0), delivered_at, 103)
                ELSE TRY_CONVERT(datetime2(0), NULLIF(TRIM(delivered_at), ''), 120)
           END AS delivered_at_raw,
           CASE WHEN promised_delivery_date LIKE '__/__/____'
                THEN TRY_CONVERT(date, promised_delivery_date, 103)
                ELSE TRY_CONVERT(date, promised_delivery_date, 23)
           END AS promised_date,
           LOWER(TRIM(shipping_city)) AS city_key,
           LOWER(TRIM(payment_method)) AS pay_raw,
           LOWER(TRIM(order_status)) AS status_raw,
           NULLIF(NULLIF(UPPER(TRIM(promo_code)), ''), 'NONE') AS promo_code,
           courier,
           TRY_CONVERT(int, REPLACE(REPLACE(shipping_fee, 'Rs.', ''), ' ', '')) AS shipping_fee
    FROM dedup
    WHERE customer_id NOT LIKE 'TEST%'
)
SELECT p.order_id,
       COALESCE(idm.customer_id, p.raw_customer_id) AS customer_id,
       p.ordered_at,
       CAST(p.ordered_at AS date) AS order_date,
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
       CAST(CASE WHEN p.delivered_at_raw < p.ordered_at THEN 1 ELSE 0 END AS bit) AS delivered_before_ordered,
       CASE WHEN p.status_raw IN ('dlvd', 'delivered') THEN 'Delivered'
            WHEN p.status_raw IN ('cncl', 'cancelled', 'canceled') THEN 'Cancelled'
            WHEN p.status_raw IN ('rto', 'returned_to_origin') THEN 'Returned to Origin'
            WHEN p.status_raw IN ('shpd', 'shipped') THEN 'In Transit'
       END AS order_status,
       p.shipping_fee,
       CAST(CASE WHEN p.ordered_at < '2025-01-01' THEN 1 ELSE 0 END AS bit) AS from_legacy_system
INTO clean.orders
FROM parsed p
LEFT JOIN clean.customer_id_map idm ON idm.raw_customer_id = p.raw_customer_id
LEFT JOIN clean.customers c ON c.customer_id = COALESCE(idm.customer_id, p.raw_customer_id)
LEFT JOIN clean.city_map m ON m.raw_key = p.city_key;
GO

DROP TABLE IF EXISTS clean.order_items;
GO
WITH typed AS (
    SELECT i.order_item_id,
           i.order_id,
           i.product_id,
           TRY_CONVERT(int, i.quantity) AS quantity,
           TRY_CONVERT(decimal(14, 2), i.unit_price) AS unit_price_raw,
           TRY_CONVERT(int, i.discount_pct) AS discount_pct,
           p.list_price
    FROM raw.order_items i
    JOIN clean.products p ON p.product_id = i.product_id
)
SELECT order_item_id,
       order_id,
       product_id,
       quantity,
       discount_pct,
       CAST(CASE WHEN unit_price_raw > 50 * list_price THEN ROUND(unit_price_raw / 100, 2)
                 WHEN unit_price_raw > 5 * list_price THEN ROUND(unit_price_raw / 10, 2)
                 ELSE unit_price_raw
            END AS decimal(14, 2)) AS unit_price,
       CAST(CASE WHEN unit_price_raw > 5 * list_price THEN 1 ELSE 0 END AS bit) AS price_corrected
INTO clean.order_items
FROM typed
WHERE quantity > 0
  AND order_id IN (SELECT order_id FROM clean.orders);
GO

DROP TABLE IF EXISTS clean.returns;
GO
SELECT r.return_id,
       r.order_item_id,
       i.order_id,
       TRIM(r.return_reason) AS return_reason,
       TRY_CONVERT(date, r.return_requested_date) AS return_requested_date,
       TRY_CONVERT(decimal(14, 2), r.refund_amount) AS refund_amount
INTO clean.returns
FROM raw.returns r
JOIN clean.order_items i ON i.order_item_id = r.order_item_id;
GO

DROP TABLE IF EXISTS clean.checkout_sessions;
GO
SELECT DISTINCT
       session_id,
       customer_id,
       TRY_CONVERT(datetime2(0), session_start, 120) AS session_start,
       device_type,
       traffic_source,
       LOWER(TRIM(experiment_group)) AS experiment_group,
       TRY_CONVERT(int, session_duration_sec) AS session_duration_sec,
       CAST(CASE WHEN TRY_CONVERT(int, session_duration_sec) < 3 THEN 1 ELSE 0 END AS bit) AS is_bot,
       TRY_CONVERT(int, completed_order) AS completed_order,
       TRY_CONVERT(decimal(14, 2), order_value) AS order_value
INTO clean.checkout_sessions
FROM raw.checkout_sessions;
GO
