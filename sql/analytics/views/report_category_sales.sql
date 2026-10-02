-- ===========================================================================
-- View : analytics.report_category_sales
-- Purpose : rolls product revenue and demand up to category levels.
-- Run : psql -d datawarehouse -f sql/analytics/views/report_category_sales.sql
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.report_category_sales AS
WITH category_lines AS (
    SELECT
        dim_products.category,
        dim_products.subcategory,
        fact_sales.order_number,
        fact_sales.customer_key,
        fact_sales.product_key,
        fact_sales.order_date,
        fact_sales.sales_amount,
        fact_sales.quantity
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN warehouse.dim_products AS dim_products
        ON fact_sales.product_key = dim_products.product_sk
    WHERE fact_sales.order_date IS NOT NULL
)

SELECT
    category_lines.category,
    category_lines.subcategory,
    COUNT(DISTINCT category_lines.product_key) AS product_count,
    COUNT(DISTINCT category_lines.order_number) AS order_count,
    COUNT(DISTINCT category_lines.customer_key) AS customer_count,
    SUM(category_lines.sales_amount) AS total_revenue,
    SUM(category_lines.quantity) AS total_quantity,
    MAX(category_lines.order_date) AS last_sale_date,
    CASE
        WHEN COUNT(DISTINCT category_lines.order_number) = 0 THEN 0
        ELSE SUM(category_lines.sales_amount) / COUNT(DISTINCT category_lines.order_number)
    END AS avg_order_revenue
FROM category_lines

GROUP BY
    category_lines.category,
    category_lines.subcategory

ORDER BY
    total_revenue DESC;
