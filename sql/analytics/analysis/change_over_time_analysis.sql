-- ===========================================================================
-- Analysis : change over time analysis
-- Purpose : tracks sales trends and seasonality across time grains.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/change_over_time_analysis.sql
-- ===========================================================================

-- ===========================================================================
-- Sales performance by order year and month.
-- ===========================================================================
SELECT
    DATE_PART('year', fact_sales.order_date)::INT AS order_year,
    DATE_PART('month', fact_sales.order_date)::INT AS order_month,
    SUM(fact_sales.sales_amount) AS total_sales,
    COUNT(DISTINCT fact_sales.customer_key) AS total_customers,
    SUM(fact_sales.quantity) AS total_quantity
FROM warehouse.fact_sales AS fact_sales
WHERE fact_sales.order_date IS NOT NULL

GROUP BY
    DATE_PART('year', fact_sales.order_date),
    DATE_PART('month', fact_sales.order_date)

ORDER BY
    DATE_PART('year', fact_sales.order_date),
    DATE_PART('month', fact_sales.order_date);

-- ===========================================================================
-- Sales performance truncated to order month.
-- ===========================================================================
SELECT
    DATE_TRUNC('month', fact_sales.order_date)::DATE AS order_month,
    SUM(fact_sales.sales_amount) AS total_sales,
    COUNT(DISTINCT fact_sales.customer_key) AS total_customers,
    SUM(fact_sales.quantity) AS total_quantity
FROM warehouse.fact_sales AS fact_sales
WHERE fact_sales.order_date IS NOT NULL

GROUP BY
    DATE_TRUNC('month', fact_sales.order_date)

ORDER BY
    DATE_TRUNC('month', fact_sales.order_date);

-- ===========================================================================
-- Sales performance by formatted order month label.
-- ===========================================================================
SELECT
    TO_CHAR(fact_sales.order_date, 'YYYY-Mon') AS order_month_label,
    SUM(fact_sales.sales_amount) AS total_sales,
    COUNT(DISTINCT fact_sales.customer_key) AS total_customers,
    SUM(fact_sales.quantity) AS total_quantity
FROM warehouse.fact_sales AS fact_sales
WHERE fact_sales.order_date IS NOT NULL

GROUP BY
    TO_CHAR(fact_sales.order_date, 'YYYY-Mon')

ORDER BY
    TO_CHAR(fact_sales.order_date, 'YYYY-Mon');
