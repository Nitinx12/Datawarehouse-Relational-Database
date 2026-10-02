-- ===========================================================================
-- Script : 02_lp_check_customer_report
-- Purpose : validates customer segments and reconciles revenue to the fact.
-- Run : psql -d datawarehouse -f tests/data_quality/analytics/02_lp_check_customer_report.sql
-- ===========================================================================

DO $$
DECLARE
    bad_segments BIGINT;
    bad_vip BIGINT;
    bad_regular BIGINT;
    bad_new BIGINT;
    report_total NUMERIC;
    fact_total NUMERIC;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Customer Report';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO bad_segments
    FROM analytics.report_customers
    WHERE customer_segment IS NULL
        OR customer_segment NOT IN ('VIP', 'Regular', 'New');

    SELECT COUNT(*)
    INTO bad_vip
    FROM analytics.report_customers
    WHERE customer_segment = 'VIP'
        AND (lifespan_months < 12 OR total_sales <= 5000);

    SELECT COUNT(*)
    INTO bad_regular
    FROM analytics.report_customers
    WHERE customer_segment = 'Regular'
        AND (lifespan_months < 12 OR total_sales > 5000);

    SELECT COUNT(*)
    INTO bad_new
    FROM analytics.report_customers
    WHERE customer_segment = 'New'
        AND lifespan_months >= 12;

    RAISE NOTICE '  Bad segments: %, bad VIP: %, bad Regular: %, bad New: %', bad_segments, bad_vip, bad_regular, bad_new;

    IF bad_segments > 0 OR bad_vip > 0 OR bad_regular > 0 OR bad_new > 0 THEN
        RAISE EXCEPTION 'Customer segment check FAILED: segments=% vip=% regular=% new=%', bad_segments, bad_vip, bad_regular, bad_new;
    ELSE
        RAISE NOTICE '  Customer segments are consistent.';
    END IF;

    SELECT COALESCE(SUM(total_sales), 0)
    INTO report_total
    FROM analytics.report_customers;

    SELECT COALESCE(SUM(sales_amount), 0)
    INTO fact_total
    FROM warehouse.fact_sales
    WHERE order_date IS NOT NULL;

    RAISE NOTICE '  Report total: %, fact total: %', report_total, fact_total;

    IF report_total <> fact_total THEN
        RAISE EXCEPTION 'Customer revenue reconciliation FAILED: report=% fact=%', report_total, fact_total;
    ELSE
        RAISE NOTICE '  Customer revenue reconciles exactly.';
    END IF;
END $$;
