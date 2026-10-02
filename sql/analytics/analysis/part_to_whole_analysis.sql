-- ===========================================================================
-- Analysis : part to whole analysis
-- Purpose : measures each category contribution to overall sales.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/part_to_whole_analysis.sql
-- ===========================================================================

-- ===========================================================================
-- Category share of overall sales with percentage of total.
-- ===========================================================================
WITH category_sales AS (
    SELECT
        dim_products.category,
        SUM(fact_sales.sales_amount) AS total_sales
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN warehouse.dim_products AS dim_products
        ON fact_sales.product_key = dim_products.product_sk

    GROUP BY
        dim_products.category
)

SELECT
    category_sales.category,
    category_sales.total_sales,
    SUM(category_sales.total_sales) OVER () AS overall_sales,
    ROUND(category_sales.total_sales / SUM(category_sales.total_sales) OVER () * 100, 2) AS percentage_of_total
FROM category_sales

ORDER BY
    category_sales.total_sales DESC;
