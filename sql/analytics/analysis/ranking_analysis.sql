-- ===========================================================================
-- Analysis : ranking analysis
-- Purpose : ranks products and customers to surface top and bottom performers.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/ranking_analysis.sql
-- ===========================================================================

-- ===========================================================================
-- Five products generating the highest revenue, simple ranking.
-- ===========================================================================
SELECT
    dim_products.product_name,
    SUM(fact_sales.sales_amount) AS total_revenue
FROM warehouse.fact_sales AS fact_sales
LEFT JOIN warehouse.dim_products AS dim_products
    ON fact_sales.product_key = dim_products.product_sk

GROUP BY
    dim_products.product_name

ORDER BY
    total_revenue DESC

LIMIT 5;

-- ===========================================================================
-- Five products generating the highest revenue, window ranking.
-- ===========================================================================
SELECT
    ranked_products.product_name,
    ranked_products.total_revenue,
    ranked_products.product_rank
FROM (
    SELECT
        dim_products.product_name,
        SUM(fact_sales.sales_amount) AS total_revenue,
        RANK() OVER (
            ORDER BY SUM(fact_sales.sales_amount) DESC
        ) AS product_rank
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN warehouse.dim_products AS dim_products
        ON fact_sales.product_key = dim_products.product_sk

    GROUP BY
        dim_products.product_name
) AS ranked_products
WHERE ranked_products.product_rank <= 5

ORDER BY
    ranked_products.product_rank ASC;

-- ===========================================================================
-- Five worst-performing products in terms of sales.
-- ===========================================================================
SELECT
    dim_products.product_name,
    SUM(fact_sales.sales_amount) AS total_revenue
FROM warehouse.fact_sales AS fact_sales
LEFT JOIN warehouse.dim_products AS dim_products
    ON fact_sales.product_key = dim_products.product_sk

GROUP BY
    dim_products.product_name

ORDER BY
    total_revenue ASC

LIMIT 5;

-- ===========================================================================
-- Ten customers who have generated the highest revenue.
-- ===========================================================================
SELECT
    dim_customers.customer_key,
    dim_customers.first_name,
    dim_customers.last_name,
    SUM(fact_sales.sales_amount) AS total_revenue
FROM warehouse.fact_sales AS fact_sales
LEFT JOIN warehouse.dim_customers AS dim_customers
    ON fact_sales.customer_key = dim_customers.customer_sk

GROUP BY
    dim_customers.customer_key,
    dim_customers.first_name,
    dim_customers.last_name

ORDER BY
    total_revenue DESC

LIMIT 10;

-- ===========================================================================
-- Three customers with the fewest orders placed.
-- ===========================================================================
SELECT
    dim_customers.customer_key,
    dim_customers.first_name,
    dim_customers.last_name,
    COUNT(DISTINCT fact_sales.order_number) AS total_orders
FROM warehouse.fact_sales AS fact_sales
LEFT JOIN warehouse.dim_customers AS dim_customers
    ON fact_sales.customer_key = dim_customers.customer_sk

GROUP BY
    dim_customers.customer_key,
    dim_customers.first_name,
    dim_customers.last_name

ORDER BY
    total_orders ASC

LIMIT 3;
