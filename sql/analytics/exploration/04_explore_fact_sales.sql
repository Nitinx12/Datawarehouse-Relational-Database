-- ===========================================================================
-- Script : 04_explore_fact_sales
-- Purpose : profiles the warehouse sales fact grain, dates, and measures.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/04_explore_fact_sales.sql
-- ===========================================================================

-- ===========================================================================
-- Row, date-range, and measure profile of warehouse.fact_sales.
-- ===========================================================================
SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT fact_sales.order_number) AS distinct_orders,
    MIN(fact_sales.order_date) AS min_order_date,
    MAX(fact_sales.order_date) AS max_order_date,
    MIN(fact_sales.shipping_date) AS min_shipping_date,
    MAX(fact_sales.shipping_date) AS max_shipping_date,
    SUM(fact_sales.sales_amount) AS total_sales_amount,
    SUM(fact_sales.quantity) AS total_quantity,
    AVG(fact_sales.price) AS avg_price,
    COUNT(fact_sales.product_key) FILTER (WHERE fact_sales.product_key IS NULL) AS null_product_keys,
    COUNT(fact_sales.customer_key) FILTER (WHERE fact_sales.customer_key IS NULL) AS null_customer_keys
FROM warehouse.fact_sales AS fact_sales;

-- ===========================================================================
-- Monthly order volume and revenue from warehouse.fact_sales.
-- ===========================================================================
SELECT
    DATE_TRUNC('month', fact_sales.order_date)::DATE AS order_month,
    COUNT(*) AS line_count,
    COUNT(DISTINCT fact_sales.order_number) AS order_count,
    SUM(fact_sales.sales_amount) AS total_sales_amount
FROM warehouse.fact_sales AS fact_sales
WHERE fact_sales.order_date IS NOT NULL

GROUP BY
    DATE_TRUNC('month', fact_sales.order_date)::DATE

ORDER BY
    order_month;
