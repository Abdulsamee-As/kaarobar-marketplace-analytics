SELECT 'clean.orders: order_id is unique' AS check_name,
       COUNT(*) - COUNT(DISTINCT order_id) AS failing_rows
FROM clean.orders
UNION ALL
SELECT 'clean.orders: every timestamp parsed',
       SUM(CASE WHEN ordered_at IS NULL THEN 1 ELSE 0 END) FROM clean.orders
UNION ALL
SELECT 'clean.orders: every payment label mapped',
       SUM(CASE WHEN payment_method IS NULL THEN 1 ELSE 0 END) FROM clean.orders
UNION ALL
SELECT 'clean.orders: every status label mapped',
       SUM(CASE WHEN order_status IS NULL THEN 1 ELSE 0 END) FROM clean.orders
UNION ALL
SELECT 'clean.orders: no delivery before the order',
       SUM(CASE WHEN delivered_at < ordered_at THEN 1 ELSE 0 END) FROM clean.orders
UNION ALL
SELECT 'clean.orders: no QA test accounts',
       SUM(CASE WHEN customer_id LIKE 'TEST%' THEN 1 ELSE 0 END) FROM clean.orders
UNION ALL
SELECT 'clean.orders: every customer exists',
       SUM(CASE WHEN c.customer_id IS NULL THEN 1 ELSE 0 END)
FROM clean.orders o LEFT JOIN clean.customers c ON c.customer_id = o.customer_id
UNION ALL
SELECT 'clean.customers: one account per email',
       COUNT(*) - COUNT(DISTINCT email) FROM clean.customers
UNION ALL
SELECT 'clean.products: every category mapped',
       SUM(CASE WHEN category IS NULL THEN 1 ELSE 0 END) FROM clean.products
UNION ALL
SELECT 'clean.order_items: quantity is positive',
       SUM(CASE WHEN quantity <= 0 THEN 1 ELSE 0 END) FROM clean.order_items
UNION ALL
SELECT 'clean.order_items: price never above list price',
       SUM(CASE WHEN i.unit_price > p.list_price THEN 1 ELSE 0 END)
FROM clean.order_items i JOIN clean.products p ON p.product_id = i.product_id
UNION ALL
SELECT 'clean.order_items: every item has an order',
       SUM(CASE WHEN o.order_id IS NULL THEN 1 ELSE 0 END)
FROM clean.order_items i LEFT JOIN clean.orders o ON o.order_id = i.order_id
UNION ALL
SELECT 'clean.returns: every return has an item',
       SUM(CASE WHEN i.order_item_id IS NULL THEN 1 ELSE 0 END)
FROM clean.returns r LEFT JOIN clean.order_items i ON i.order_item_id = r.order_item_id
UNION ALL
SELECT 'clean.checkout_sessions: session_id is unique',
       COUNT(*) - COUNT(DISTINCT session_id) FROM clean.checkout_sessions
UNION ALL
SELECT 'clean.checkout_sessions: group is control or treatment',
       SUM(CASE WHEN experiment_group NOT IN ('control', 'treatment') THEN 1 ELSE 0 END) FROM clean.checkout_sessions
UNION ALL
SELECT 'mart.fact_orders: net revenue never negative',
       SUM(CASE WHEN net_revenue < 0 THEN 1 ELSE 0 END) FROM mart.fact_orders
UNION ALL
SELECT 'clean.orders: city known (warning)',
       SUM(CASE WHEN city IS NULL THEN 1 ELSE 0 END) FROM clean.orders
UNION ALL
SELECT 'clean.orders: delivered with no delivery time (warning)',
       SUM(CASE WHEN order_status = 'Delivered' AND delivered_at IS NULL THEN 1 ELSE 0 END) FROM clean.orders;
