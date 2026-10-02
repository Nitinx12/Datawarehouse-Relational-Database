-- ===========================================================================
-- Analysis : cumulative analysis
-- Purpose : tracks running sales totals and moving average prices over time.
-- Run : psql -d datawarehouse -f sql/analytics/analysis/cumulative_analysis.sql
-- ===========================================================================

-- ===========================================================================
-- Total sales per year with running total and moving average price.
-- ===========================================================================
SELECT
    yearly_sales.order_date,
    yearly_sales.total_sales,
    SUM(yearly_sales.total_sales) OVER (
        ORDER BY yearly_sales.order_date
    ) AS running_total_sales,
    AVG(yearly_sales.avg_price) OVER (
        ORDER BY yearly_sales.order_date
    ) AS moving_average_price
FROM (
    SELECT
        DATE_TRUNC('year', fact_sales.order_date)::DATE AS order_date,
        SUM(fact_sales.sales_amount) AS total_sales,
        AVG(fact_sales.price) AS avg_price
    FROM warehouse.fact_sales AS fact_sales
    WHERE fact_sales.order_date IS NOT NULL

    GROUP BY
        DATE_TRUNC('year', fact_sales.order_date)
) AS yearly_sales

ORDER BY
    yearly_sales.order_date;
