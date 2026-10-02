-- ===========================================================================
-- View : analytics.report_customers
-- Purpose : consolidates customer metrics, segments, and KPIs.
-- Run : psql -d datawarehouse -f sql/analytics/views/report_customers.sql
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.report_customers AS
WITH base_orders AS (
    SELECT
        fact_sales.order_number,
        fact_sales.product_key,
        fact_sales.order_date,
        fact_sales.sales_amount,
        fact_sales.quantity,
        dim_customers.customer_sk,
        dim_customers.customer_key,
        dim_customers.cst_id,
        dim_customers.birthdate,
        CONCAT(dim_customers.first_name, ' ', dim_customers.last_name) AS customer_name,
        DATE_PART('year', AGE(CURRENT_DATE, dim_customers.birthdate))::INT AS age
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN warehouse.dim_customers AS dim_customers
        ON fact_sales.customer_key = dim_customers.customer_sk
    WHERE fact_sales.order_date IS NOT NULL
),

customer_aggregation AS (
    SELECT
        base_orders.customer_sk,
        base_orders.customer_key,
        base_orders.cst_id,
        base_orders.customer_name,
        base_orders.birthdate,
        base_orders.age,
        COUNT(DISTINCT base_orders.order_number) AS total_orders,
        SUM(base_orders.sales_amount) AS total_sales,
        SUM(base_orders.quantity) AS total_quantity,
        COUNT(DISTINCT base_orders.product_key) AS total_products,
        MAX(base_orders.order_date) AS last_order_date,
        (
            DATE_PART('year', AGE(MAX(base_orders.order_date), MIN(base_orders.order_date))) * 12
            + DATE_PART('month', AGE(MAX(base_orders.order_date), MIN(base_orders.order_date)))
        )::INT AS lifespan_months
    FROM base_orders

    GROUP BY
        base_orders.customer_sk,
        base_orders.customer_key,
        base_orders.cst_id,
        base_orders.customer_name,
        base_orders.birthdate,
        base_orders.age
)

SELECT
    customer_aggregation.customer_sk,
    customer_aggregation.customer_key,
    customer_aggregation.cst_id,
    customer_aggregation.customer_name,
    customer_aggregation.birthdate,
    customer_aggregation.age,
    customer_aggregation.last_order_date,
    customer_aggregation.total_orders,
    customer_aggregation.total_sales,
    customer_aggregation.total_quantity,
    customer_aggregation.total_products,
    customer_aggregation.lifespan_months,
    CASE
        WHEN customer_aggregation.age < 20 THEN 'Under 20'
        WHEN customer_aggregation.age BETWEEN 20 AND 29 THEN '20-29'
        WHEN customer_aggregation.age BETWEEN 30 AND 39 THEN '30-39'
        WHEN customer_aggregation.age BETWEEN 40 AND 49 THEN '40-49'
        ELSE '50 and above'
    END AS age_group,
    CASE
        WHEN customer_aggregation.lifespan_months >= 12 AND customer_aggregation.total_sales > 5000 THEN 'VIP'
        WHEN customer_aggregation.lifespan_months >= 12 AND customer_aggregation.total_sales <= 5000 THEN 'Regular'
        ELSE 'New'
    END AS customer_segment,
    (
        DATE_PART('year', AGE(CURRENT_DATE, customer_aggregation.last_order_date)) * 12
        + DATE_PART('month', AGE(CURRENT_DATE, customer_aggregation.last_order_date))
    )::INT AS recency_months,
    CASE
        WHEN customer_aggregation.total_orders = 0 THEN 0
        ELSE customer_aggregation.total_sales / customer_aggregation.total_orders
    END AS avg_order_value,
    CASE
        WHEN customer_aggregation.lifespan_months = 0 THEN customer_aggregation.total_sales
        ELSE customer_aggregation.total_sales / customer_aggregation.lifespan_months
    END AS avg_monthly_spend
FROM customer_aggregation;
