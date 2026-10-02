-- ===========================================================================
-- Script : 03_lp_check_product_report
-- Purpose : validates product segments against their revenue thresholds.
-- Run : psql -d datawarehouse -f tests/data_quality/analytics/03_lp_check_product_report.sql
-- ===========================================================================

DO $$
DECLARE
    bad_segments BIGINT;
    bad_high BIGINT;
    bad_mid BIGINT;
    bad_low BIGINT;
    report_total NUMERIC;
    fact_total NUMERIC;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Product Report';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO bad_segments
    FROM analytics.report_products
    WHERE product_segment IS NULL
        OR product_segment NOT IN ('High-Performer', 'Mid-Range', 'Low-Performer');

    SELECT COUNT(*)
    INTO bad_high
    FROM analytics.report_products
    WHERE product_segment = 'High-Performer'
        AND total_sales <= 50000;

    SELECT COUNT(*)
    INTO bad_mid
    FROM analytics.report_products
    WHERE product_segment = 'Mid-Range'
        AND (total_sales < 10000 OR total_sales > 50000);

    SELECT COUNT(*)
    INTO bad_low
    FROM analytics.report_products
    WHERE product_segment = 'Low-Performer'
        AND total_sales >= 10000;

    RAISE NOTICE '  Bad segments: %, bad High: %, bad Mid: %, bad Low: %', bad_segments, bad_high, bad_mid, bad_low;

    IF bad_segments > 0 OR bad_high > 0 OR bad_mid > 0 OR bad_low > 0 THEN
        RAISE EXCEPTION 'Product segment check FAILED: segments=% high=% mid=% low=%', bad_segments, bad_high, bad_mid, bad_low;
    ELSE
        RAISE NOTICE '  Product segments are consistent.';
    END IF;

    SELECT COALESCE(SUM(total_sales), 0)
    INTO report_total
    FROM analytics.report_products;

    SELECT COALESCE(SUM(sales_amount), 0)
    INTO fact_total
    FROM warehouse.fact_sales
    WHERE order_date IS NOT NULL;

    RAISE NOTICE '  Report total: %, fact total: %', report_total, fact_total;

    IF report_total <> fact_total THEN
        RAISE EXCEPTION 'Product revenue reconciliation FAILED: report=% fact=%', report_total, fact_total;
    ELSE
        RAISE NOTICE '  Product revenue reconciles exactly.';
    END IF;
END $$;
