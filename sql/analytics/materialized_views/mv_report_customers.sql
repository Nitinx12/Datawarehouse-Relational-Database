-- ===========================================================================
-- View : analytics.mv_report_customers
-- Purpose : caches the customer report for fast repeated BI reads.
-- Run : psql -d datawarehouse -f sql/analytics/views/report_customers.sql
-- Then : psql -d datawarehouse -f sql/analytics/materialized_views/mv_report_customers.sql
-- Refresh : REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_report_customers;
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_report_customers;

CREATE MATERIALIZED VIEW analytics.mv_report_customers AS
SELECT
    report_customers.customer_sk,
    report_customers.customer_key,
    report_customers.cst_id,
    report_customers.customer_name,
    report_customers.birthdate,
    report_customers.age,
    report_customers.last_order_date,
    report_customers.total_orders,
    report_customers.total_sales,
    report_customers.total_quantity,
    report_customers.total_products,
    report_customers.lifespan_months,
    report_customers.age_group,
    report_customers.customer_segment,
    report_customers.recency_months,
    report_customers.avg_order_value,
    report_customers.avg_monthly_spend
FROM analytics.report_customers AS report_customers
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_report_customers_customer_sk
    ON analytics.mv_report_customers (customer_sk);
