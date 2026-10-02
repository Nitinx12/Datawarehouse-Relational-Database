-- ===========================================================================
-- Analysis : data segmentation analysis
-- Purpose : groups products and customers into business segments.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/segmentation_analysis.sql
-- ===========================================================================

-- ===========================================================================
-- Products segmented into cost ranges.
-- ===========================================================================
WITH product_segments AS (
    SELECT
        dim_products.product_sk,
        dim_products.product_name,
        dim_products.cost,
        CASE
            WHEN dim_products.cost < 100 THEN 'Below 100'
            WHEN dim_products.cost BETWEEN 100 AND 500 THEN '100-500'
            WHEN dim_products.cost BETWEEN 500 AND 1000 THEN '500-1000'
            ELSE 'Above 1000'
        END AS cost_range
    FROM warehouse.dim_products AS dim_products
)

SELECT
    product_segments.cost_range,
    COUNT(product_segments.product_sk) AS total_products
FROM product_segments

GROUP BY
    product_segments.cost_range

ORDER BY
    total_products DESC;

-- ===========================================================================
-- Customers segmented by spending behavior into VIP, Regular, and New.
-- ===========================================================================
WITH customer_spending AS (
    SELECT
        dim_customers.customer_key,
        SUM(fact_sales.sales_amount) AS total_spending,
        MIN(fact_sales.order_date) AS first_order,
        MAX(fact_sales.order_date) AS last_order,
        (
            DATE_PART('year', AGE(MAX(fact_sales.order_date), MIN(fact_sales.order_date))) * 12
            + DATE_PART('month', AGE(MAX(fact_sales.order_date), MIN(fact_sales.order_date)))
        )::INT AS lifespan_months
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN warehouse.dim_customers AS dim_customers
        ON fact_sales.customer_key = dim_customers.customer_sk

    GROUP BY
        dim_customers.customer_key
)

SELECT
    segmented_customers.customer_segment,
    COUNT(segmented_customers.customer_key) AS total_customers
FROM (
    SELECT
        customer_spending.customer_key,
        CASE
            WHEN customer_spending.lifespan_months >= 12 AND customer_spending.total_spending > 5000 THEN 'VIP'
            WHEN customer_spending.lifespan_months >= 12 AND customer_spending.total_spending <= 5000 THEN 'Regular'
            ELSE 'New'
        END AS customer_segment
    FROM customer_spending
) AS segmented_customers

GROUP BY
    segmented_customers.customer_segment

ORDER BY
    total_customers DESC;
