-- ===========================================================================
-- Script : 06_lp_check_kpi_math
-- Purpose : spot-checks KPI formulas and category share totals.
-- Run : psql -d datawarehouse -f tests/data_quality/analytics/06_lp_check_kpi_math.sql
-- ===========================================================================

DO $$
DECLARE
    bad_customer_avg BIGINT;
    negative_lifespan BIGINT;
    negative_recency BIGINT;
    bad_age_group BIGINT;
    bad_product_avg BIGINT;
    share_drift NUMERIC;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking KPI Math';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO bad_customer_avg
    FROM analytics.report_customers
    WHERE total_orders > 0
        AND total_sales IS NOT NULL
        AND ABS(total_sales - avg_order_value * total_orders) > 0.01;

    SELECT COUNT(*)
    INTO negative_lifespan
    FROM analytics.report_customers
    WHERE lifespan_months < 0;

    SELECT COUNT(*)
    INTO negative_recency
    FROM analytics.report_customers
    WHERE recency_months < 0;

    SELECT COUNT(*)
    INTO bad_age_group
    FROM analytics.report_customers
    WHERE (age < 20 AND age_group <> 'Under 20')
        OR (age BETWEEN 20 AND 29 AND age_group <> '20-29')
        OR (age BETWEEN 30 AND 39 AND age_group <> '30-39')
        OR (age BETWEEN 40 AND 49 AND age_group <> '40-49')
        OR (age >= 50 AND age_group <> '50 and above');

    SELECT COUNT(*)
    INTO bad_product_avg
    FROM analytics.report_products
    WHERE total_orders > 0
        AND total_sales IS NOT NULL
        AND ABS(total_sales - avg_order_revenue * total_orders) > 0.01;

    SELECT ABS(COALESCE(SUM(percentage_of_total), 0) - 100)
    INTO share_drift
    FROM analytics.report_category_sales;

    RAISE NOTICE '  Bad customer avg: %, negative lifespan: %, negative recency: %', bad_customer_avg, negative_lifespan, negative_recency;
    RAISE NOTICE '  Bad age group: %, bad product avg: %, share drift: %', bad_age_group, bad_product_avg, share_drift;

    IF bad_customer_avg > 0 OR negative_lifespan > 0 OR negative_recency > 0 THEN
        RAISE EXCEPTION 'Customer KPI check FAILED: avg=% lifespan=% recency=%', bad_customer_avg, negative_lifespan, negative_recency;
    ELSE
        RAISE NOTICE '  Customer KPIs are consistent.';
    END IF;

    IF bad_age_group > 0 OR bad_product_avg > 0 THEN
        RAISE EXCEPTION 'Product KPI check FAILED: age=% avg=%', bad_age_group, bad_product_avg;
    ELSE
        RAISE NOTICE '  Product KPIs are consistent.';
    END IF;

    IF share_drift > 0.5 THEN
        RAISE EXCEPTION 'Category share check FAILED: drift=%', share_drift;
    ELSE
        RAISE NOTICE '  Category shares sum to 100.';
    END IF;
END $$;
