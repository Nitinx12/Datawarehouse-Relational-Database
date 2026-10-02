-- ===========================================================================
-- Script : 05_lp_check_monthly_snapshot
-- Purpose : validates the KPI snapshot matches the monthly trend view.
-- Run : psql -d datawarehouse -f tests/data_quality/analytics/05_lp_check_monthly_snapshot.sql
-- ===========================================================================

DO $$
DECLARE
    missing_months BIGINT;
    drift_months BIGINT;
    null_loaded BIGINT;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Monthly Snapshot';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO missing_months
    FROM analytics.report_sales_monthly AS trend
    LEFT JOIN analytics.monthly_kpi_snapshot AS snapshot
        ON snapshot.snapshot_month = trend.order_month
    WHERE snapshot.snapshot_month IS NULL;

    SELECT COUNT(*)
    INTO drift_months
    FROM analytics.report_sales_monthly AS trend
    JOIN analytics.monthly_kpi_snapshot AS snapshot
        ON snapshot.snapshot_month = trend.order_month
    WHERE snapshot.total_revenue IS DISTINCT FROM trend.total_revenue
        OR snapshot.order_count IS DISTINCT FROM trend.order_count
        OR snapshot.customer_count IS DISTINCT FROM trend.customer_count;

    SELECT COUNT(*)
    INTO null_loaded
    FROM analytics.monthly_kpi_snapshot
    WHERE loaded_at IS NULL;

    RAISE NOTICE '  Missing months: %, drift months: %, null loaded: %', missing_months, drift_months, null_loaded;

    IF missing_months > 0 OR drift_months > 0 OR null_loaded > 0 THEN
        RAISE EXCEPTION 'Monthly snapshot check FAILED: missing=% drift=% loaded=%', missing_months, drift_months, null_loaded;
    ELSE
        RAISE NOTICE '  Monthly snapshot matches the trend view.';
    END IF;
END $$;
