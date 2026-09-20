-- =====================================================================
-- 00_load_sqlserver.sql : load the raw CSV extracts into SQL Server
-- Every column is text, exactly as delivered. Typing happens in
-- 02_clean.sql, where bad values can be caught instead of crashing the load.
-- src/run_pipeline.py passes the data folder in the DataDir variable.
-- Dialect: T-SQL (SQL Server 2017 or later).
-- =====================================================================
IF SCHEMA_ID('raw') IS NULL EXEC('CREATE SCHEMA raw');
GO

DROP TABLE IF EXISTS raw.customers;
CREATE TABLE raw.customers (
    customer_id NVARCHAR(50), email NVARCHAR(200), signup_date NVARCHAR(50),
    city NVARCHAR(100), acquisition_channel NVARCHAR(100), device_type NVARCHAR(50));
GO
BULK INSERT raw.customers FROM '$(DataDir)customers.csv'
    WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', CODEPAGE = '65001', ROWTERMINATOR = '0x0d0a', TABLOCK);
GO

DROP TABLE IF EXISTS raw.sellers;
CREATE TABLE raw.sellers (
    seller_id NVARCHAR(50), seller_name NVARCHAR(200), seller_city NVARCHAR(100),
    joined_date NVARCHAR(50), seller_type NVARCHAR(100));
GO
BULK INSERT raw.sellers FROM '$(DataDir)sellers.csv'
    WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', CODEPAGE = '65001', ROWTERMINATOR = '0x0d0a', TABLOCK);
GO

DROP TABLE IF EXISTS raw.products;
CREATE TABLE raw.products (
    product_id NVARCHAR(50), product_name NVARCHAR(200), category NVARCHAR(100),
    subcategory NVARCHAR(100), brand NVARCHAR(100), seller_id NVARCHAR(50),
    list_price NVARCHAR(50), unit_cost NVARCHAR(50));
GO
BULK INSERT raw.products FROM '$(DataDir)products.csv'
    WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', CODEPAGE = '65001', ROWTERMINATOR = '0x0d0a', TABLOCK);
GO

DROP TABLE IF EXISTS raw.orders;
CREATE TABLE raw.orders (
    order_id NVARCHAR(50), customer_id NVARCHAR(50), order_datetime NVARCHAR(50),
    shipping_city NVARCHAR(100), payment_method NVARCHAR(50), promo_code NVARCHAR(50),
    courier NVARCHAR(50), promised_delivery_date NVARCHAR(50), delivered_at NVARCHAR(50),
    order_status NVARCHAR(50), shipping_fee NVARCHAR(50));
GO
BULK INSERT raw.orders FROM '$(DataDir)orders.csv'
    WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', CODEPAGE = '65001', ROWTERMINATOR = '0x0d0a', TABLOCK);
GO

DROP TABLE IF EXISTS raw.order_items;
CREATE TABLE raw.order_items (
    order_item_id NVARCHAR(50), order_id NVARCHAR(50), product_id NVARCHAR(50),
    quantity NVARCHAR(50), unit_price NVARCHAR(50), discount_pct NVARCHAR(50));
GO
BULK INSERT raw.order_items FROM '$(DataDir)order_items.csv'
    WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', CODEPAGE = '65001', ROWTERMINATOR = '0x0d0a', TABLOCK);
GO

DROP TABLE IF EXISTS raw.returns;
CREATE TABLE raw.returns (
    return_id NVARCHAR(50), order_item_id NVARCHAR(50), order_id NVARCHAR(50),
    return_reason NVARCHAR(100), return_requested_date NVARCHAR(50), refund_amount NVARCHAR(50));
GO
BULK INSERT raw.returns FROM '$(DataDir)returns.csv'
    WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', CODEPAGE = '65001', ROWTERMINATOR = '0x0d0a', TABLOCK);
GO

DROP TABLE IF EXISTS raw.checkout_sessions;
CREATE TABLE raw.checkout_sessions (
    session_id NVARCHAR(50), customer_id NVARCHAR(50), session_start NVARCHAR(50),
    device_type NVARCHAR(50), traffic_source NVARCHAR(50), experiment_group NVARCHAR(50),
    session_duration_sec NVARCHAR(50), completed_order NVARCHAR(50), order_value NVARCHAR(50));
GO
BULK INSERT raw.checkout_sessions FROM '$(DataDir)checkout_sessions.csv'
    WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', CODEPAGE = '65001', ROWTERMINATOR = '0x0d0a', TABLOCK);
GO
