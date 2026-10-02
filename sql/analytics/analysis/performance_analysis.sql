-- ===========================================================================
-- Analysis : performance analysis
-- Purpose : benchmarks yearly product sales against averages and prior years.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/performance_analysis.sql
-- ===========================================================================

WITH yearly_product_sales AS (
    SELECT
        dim_products.product_name,
        DATE_PART('year', fact_sales.order_date)::INT AS order_year,
        SUM(fact_sales.sales_amount) AS current_sales
    FROM warehouse.fact_sales AS fact_sales
    LEFT JOIN warehouse.dim_products AS dim_products
        ON fact_sales.product_key = dim_products.product_sk
    WHERE fact_sales.order_date IS NOT NULL

    GROUP BY
        DATE_PART('year', fact_sales.order_date),
        dim_products.product_name
)

-- ===========================================================================
-- Yearly product sales versus product average and previous year.
-- ===========================================================================
SELECT
    yearly_product_sales.order_year,
    yearly_product_sales.product_name,
    yearly_product_sales.current_sales,
    AVG(yearly_product_sales.current_sales) OVER (
        PARTITION BY yearly_product_sales.product_name
    ) AS avg_sales,
    yearly_product_sales.current_sales - AVG(yearly_product_sales.current_sales) OVER (
        PARTITION BY yearly_product_sales.product_name
    ) AS diff_avg,
    CASE
        WHEN yearly_product_sales.current_sales - AVG(yearly_product_sales.current_sales) OVER (
            PARTITION BY yearly_product_sales.product_name
        ) > 0 THEN 'Above Avg'
        WHEN yearly_product_sales.current_sales - AVG(yearly_product_sales.current_sales) OVER (
            PARTITION BY yearly_product_sales.product_name
        ) < 0 THEN 'Below Avg'
        ELSE 'Avg'
    END AS avg_change,
    LAG(yearly_product_sales.current_sales) OVER (
        PARTITION BY yearly_product_sales.product_name
        ORDER BY yearly_product_sales.order_year
    ) AS py_sales,
    yearly_product_sales.current_sales - LAG(yearly_product_sales.current_sales) OVER (
        PARTITION BY yearly_product_sales.product_name
        ORDER BY yearly_product_sales.order_year
    ) AS diff_py,
    CASE
        WHEN yearly_product_sales.current_sales - LAG(yearly_product_sales.current_sales) OVER (
            PARTITION BY yearly_product_sales.product_name
            ORDER BY yearly_product_sales.order_year
        ) > 0 THEN 'Increase'
        WHEN yearly_product_sales.current_sales - LAG(yearly_product_sales.current_sales) OVER (
            PARTITION BY yearly_product_sales.product_name
            ORDER BY yearly_product_sales.order_year
        ) < 0 THEN 'Decrease'
        ELSE 'No Change'
    END AS py_change
FROM yearly_product_sales

ORDER BY
    yearly_product_sales.product_name ASC,
    yearly_product_sales.order_year ASC;
