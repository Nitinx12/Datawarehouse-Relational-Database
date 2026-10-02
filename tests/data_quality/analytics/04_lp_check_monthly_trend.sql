-- ===========================================================================
-- Script : 04_lp_check_monthly_trend
-- Purpose : validates monthly trend internals and reconciles to the fact.
-- Run : psql -d datawarehouse -f tests/data_quality/analytics/04_lp_check_monthly_trend.sql
-- ===========================================================================

DO $$
DECLARE
    null_months BIGINT;
    dup_months BIGINT;
    bad_new_customers BIGINT;
    bad_avg_revenue BIGINT;
    report_total NUMERIC;
    fact_total NUMERIC;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Monthly Trend';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO null_months
    FROM analytics.report_sales_monthly
    WHERE order_month IS NULL;

    SELECT COUNT(*) - COUNT(DISTINCT order_month)
    INTO dup_months
    FROM analytics.report_sales_monthly;

    SELECT COUNT(*)
    INTO bad_new_customers
    FROM analytics.report_sales_monthly
    WHERE new_customer_count > customer_count;

    SELECT COUNT(*)
    INTO bad_avg_revenue
    FROM analytics.report_sales_monthly
    WHERE order_count > 0
        AND total_revenue IS NOT NULL
        AND ABS(total_revenue - avg_order_revenue * order_count) > 0.01;

    RAISE NOTICE '  Null months: %, dup months: %, bad new: %, bad avg: %', null_months, dup_months, bad_new_customers, bad_avg_revenue;

    IF null_months > 0 OR dup_months > 0 OR bad_new_customers > 0 OR bad_avg_revenue > 0 THEN
        RAISE EXCEPTION 'Monthly trend check FAILED: nulls=% dups=% new=% avg=%', null_months, dup_months, bad_new_customers, bad_avg_revenue;
    ELSE
        RAISE NOTICE '  Monthly trend internals are consistent.';
    END IF;

    SELECT COALESCE(SUM(total_revenue), 0)
    INTO report_total
    FROM analytics.report_sales_monthly;

    SELECT COALESCE(SUM(sales_amount), 0)
    INTO fact_total
    FROM warehouse.fact_sales
    WHERE order_date IS NOT NULL;

    RAISE NOTICE '  Report total: %, fact total: %', report_total, fact_total;

    IF report_total <> fact_total THEN
        RAISE EXCEPTION 'Monthly revenue reconciliation FAILED: report=% fact=%', report_total, fact_total;
    ELSE
        RAISE NOTICE '  Monthly revenue reconciles exactly.';
    END IF;
END $$;
