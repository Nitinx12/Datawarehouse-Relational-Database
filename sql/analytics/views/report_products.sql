-- ===========================================================================
-- View : analytics.report_products
-- Purpose : consolidates product metrics, segments, and KPIs.
-- Run : psql -d datawarehouse -f sql/analytics/views/report_products.sql
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.report_products AS
WITH base_sales AS (
    SELECT
        fact_sales.order_number,
        fact_sales.order_date,
        fact_sales.customer_key,
        fact_sales.sales_amount,
        fact_sales.quantity,
        dim_products.product_sk,
        dim_products.product_number,
        dim_products.product_name,
        dim_products.category,
        dim_products.subcategory,
        dim_products.cost
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN warehouse.dim_products AS dim_products
        ON fact_sales.product_key = dim_products.product_sk
    WHERE fact_sales.order_date IS NOT NULL
),

product_aggregation AS (
    SELECT
        base_sales.product_sk,
        base_sales.product_number,
        base_sales.product_name,
        base_sales.category,
        base_sales.subcategory,
        base_sales.cost,
        MAX(base_sales.order_date) AS last_sale_date,
        COUNT(DISTINCT base_sales.order_number) AS total_orders,
        COUNT(DISTINCT base_sales.customer_key) AS total_customers,
        SUM(base_sales.sales_amount) AS total_sales,
        SUM(base_sales.quantity) AS total_quantity,
        ROUND(AVG(base_sales.sales_amount / NULLIF(base_sales.quantity, 0)), 1) AS avg_selling_price,
        (
            DATE_PART('year', AGE(MAX(base_sales.order_date), MIN(base_sales.order_date))) * 12
            + DATE_PART('month', AGE(MAX(base_sales.order_date), MIN(base_sales.order_date)))
        )::INT AS lifespan_months
    FROM base_sales

    GROUP BY
        base_sales.product_sk,
        base_sales.product_number,
        base_sales.product_name,
        base_sales.category,
        base_sales.subcategory,
        base_sales.cost
)

SELECT
    product_aggregation.product_sk,
    product_aggregation.product_number,
    product_aggregation.product_name,
    product_aggregation.category,
    product_aggregation.subcategory,
    product_aggregation.cost,
    product_aggregation.last_sale_date,
    product_aggregation.lifespan_months,
    product_aggregation.total_orders,
    product_aggregation.total_sales,
    product_aggregation.total_quantity,
    product_aggregation.total_customers,
    product_aggregation.avg_selling_price,
    CASE
        WHEN product_aggregation.total_sales > 50000 THEN 'High-Performer'
        WHEN product_aggregation.total_sales >= 10000 THEN 'Mid-Range'
        ELSE 'Low-Performer'
    END AS product_segment,
    (
        DATE_PART('year', AGE(CURRENT_DATE, product_aggregation.last_sale_date)) * 12
        + DATE_PART('month', AGE(CURRENT_DATE, product_aggregation.last_sale_date))
    )::INT AS recency_months,
    CASE
        WHEN product_aggregation.total_orders = 0 THEN 0
        ELSE product_aggregation.total_sales / product_aggregation.total_orders
    END AS avg_order_revenue,
    CASE
        WHEN product_aggregation.lifespan_months = 0 THEN product_aggregation.total_sales
        ELSE product_aggregation.total_sales / product_aggregation.lifespan_months
    END AS avg_monthly_revenue
FROM product_aggregation;
