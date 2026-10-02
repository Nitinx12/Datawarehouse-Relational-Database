-- ===========================================================================
-- Script : 01_lp_check_analytics_views
-- Purpose : every analytics view and materialized view exists and holds rows.
-- Run : psql -d datawarehouse -f tests/data_quality/analytics/01_lp_check_analytics_views.sql
-- ===========================================================================

DO $$
DECLARE
    view_name TEXT;
    row_count BIGINT;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Analytics Views';
    RAISE NOTICE '========================================';

    FOREACH view_name IN ARRAY ARRAY['report_customers', 'report_products', 'report_sales_monthly', 'report_category_sales']
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_views
            WHERE schemaname = 'analytics'
                AND viewname = view_name
        ) THEN
            fail_msg := fail_msg || format('missing view %s; ', view_name);
            CONTINUE;
        END IF;

        EXECUTE format('SELECT COUNT(*) FROM analytics.%I', view_name)
        INTO row_count;

        RAISE NOTICE '  View analytics.%: % rows', view_name, row_count;

        IF row_count = 0 THEN
            fail_msg := fail_msg || format('empty view %s; ', view_name);
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'analytics'
            AND matviewname = 'mv_report_customers'
    ) THEN
        fail_msg := fail_msg || 'missing materialized view mv_report_customers; ';
    ELSE
        SELECT COUNT(*) INTO row_count FROM analytics.mv_report_customers;
        RAISE NOTICE '  Materialized view mv_report_customers: % rows', row_count;

        IF row_count = 0 THEN
            fail_msg := fail_msg || 'empty materialized view mv_report_customers; ';
        END IF;
    END IF;

    IF fail_msg <> '' THEN
        RAISE EXCEPTION 'Analytics views check FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE 'All analytics views contain data.';
    END IF;
END $$;
