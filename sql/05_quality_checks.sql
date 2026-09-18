-- =====================================================================
-- 05_quality_checks.sql : tests the cleaned data must pass
-- Each check returns the number of failing rows; 0 means pass.
-- Checks marked (warning) are reported but do not fail the pipeline.
-- =====================================================================
SELECT 'clean.orders: order_id is unique' AS check_name,
       COUNT(*) - COUNT(DISTINCT order_id) AS failing_rows
FROM clean.orders
UNION ALL
SELECT 'clean.orders: every timestamp parsed', COUNT(*) FILTER (WHERE ordered_at IS NULL) FROM clean.orders
UNION ALL
SELECT 'clean.orders: every payment label mapped', COUNT(*) FILTER (WHERE payment_method IS NULL) FROM clean.orders
UNION ALL
SELECT 'clean.orders: every status label mapped', COUNT(*) FILTER (WHERE order_status IS NULL) FROM clean.orders
UNION ALL
SELECT 'clean.orders: no delivery before the order', COUNT(*) FILTER (WHERE delivered_at < ordered_at) FROM clean.orders
UNION ALL
SELECT 'clean.orders: no QA test accounts', COUNT(*) FILTER (WHERE customer_id LIKE 'TEST%') FROM clean.orders
UNION ALL
SELECT 'clean.orders: every customer exists',
       COUNT(*) FILTER (WHERE c.customer_id IS NULL)
FROM clean.orders o LEFT JOIN clean.customers c ON c.customer_id = o.customer_id
UNION ALL
SELECT 'clean.customers: one account per email', COUNT(*) - COUNT(DISTINCT email) FROM clean.customers
UNION ALL
SELECT 'clean.products: every category mapped', COUNT(*) FILTER (WHERE category IS NULL) FROM clean.products
UNION ALL
SELECT 'clean.order_items: quantity is positive', COUNT(*) FILTER (WHERE quantity <= 0) FROM clean.order_items
UNION ALL
SELECT 'clean.order_items: price never above list price',
       COUNT(*) FILTER (WHERE i.unit_price > p.list_price)
FROM clean.order_items i JOIN clean.products p ON p.product_id = i.product_id
UNION ALL
SELECT 'clean.order_items: every item has an order',
       COUNT(*) FILTER (WHERE o.order_id IS NULL)
FROM clean.order_items i LEFT JOIN clean.orders o ON o.order_id = i.order_id
UNION ALL
SELECT 'clean.returns: every return has an item',
       COUNT(*) FILTER (WHERE i.order_item_id IS NULL)
FROM clean.returns r LEFT JOIN clean.order_items i ON i.order_item_id = r.order_item_id
UNION ALL
SELECT 'clean.checkout_sessions: session_id is unique',
       COUNT(*) - COUNT(DISTINCT session_id) FROM clean.checkout_sessions
UNION ALL
SELECT 'clean.checkout_sessions: group is control or treatment',
       COUNT(*) FILTER (WHERE experiment_group NOT IN ('control', 'treatment')) FROM clean.checkout_sessions
UNION ALL
SELECT 'mart.fact_orders: net revenue never negative', COUNT(*) FILTER (WHERE net_revenue < 0) FROM mart.fact_orders
UNION ALL
SELECT 'clean.orders: city known (warning)', COUNT(*) FILTER (WHERE city IS NULL) FROM clean.orders
UNION ALL
SELECT 'clean.orders: delivered with no delivery time (warning)',
       COUNT(*) FILTER (WHERE order_status = 'Delivered' AND delivered_at IS NULL) FROM clean.orders;
