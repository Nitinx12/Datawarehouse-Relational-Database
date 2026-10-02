-- ===========================================================================
-- View : analytics.report_sales_monthly
-- Purpose : tracks orders, revenue, and customer growth per order month.
-- Run : psql -d datawarehouse -f sql/analytics/views/report_sales_monthly.sql
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.report_sales_monthly AS
WITH monthly_lines AS (
    SELECT
        fact_sales.order_number,
        fact_sales.customer_key,
        fact_sales.product_key,
        fact_sales.sales_amount,
        fact_sales.quantity,
        DATE_TRUNC('month', fact_sales.order_date)::DATE AS order_month
    FROM warehouse.fact_sales AS fact_sales
    WHERE fact_sales.order_date IS NOT NULL
),

customer_first_orders AS (
    SELECT
        monthly_lines.customer_key,
        MIN(monthly_lines.order_month) AS first_order_month
    FROM monthly_lines

    GROUP BY
        monthly_lines.customer_key
)

SELECT
    monthly_lines.order_month,
    COUNT(*) AS line_count,
    COUNT(DISTINCT monthly_lines.order_number) AS order_count,
    COUNT(DISTINCT monthly_lines.customer_key) AS customer_count,
    COUNT(DISTINCT monthly_lines.product_key) AS product_count,
    SUM(monthly_lines.sales_amount) AS total_revenue,
    SUM(monthly_lines.quantity) AS total_quantity,
    COUNT(DISTINCT monthly_lines.customer_key) FILTER (
        WHERE customer_first_orders.first_order_month = monthly_lines.order_month
    ) AS new_customer_count,
    CASE
        WHEN COUNT(DISTINCT monthly_lines.order_number) = 0 THEN 0
        ELSE SUM(monthly_lines.sales_amount) / COUNT(DISTINCT monthly_lines.order_number)
    END AS avg_order_revenue
FROM monthly_lines
LEFT JOIN customer_first_orders
    ON monthly_lines.customer_key = customer_first_orders.customer_key

GROUP BY
    monthly_lines.order_month

ORDER BY
    monthly_lines.order_month;
