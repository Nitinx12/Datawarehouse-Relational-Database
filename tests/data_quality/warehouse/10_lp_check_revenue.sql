/*
===============================================================================
 Script Name : 10_lp_check_revenue.sql
 Description : Revenue reconciliation: the fact must hold exactly the
               staging sales total. Any drift means lost or doubled rows.
===============================================================================
*/

DO $$
DECLARE
    fact_total NUMERIC;
    staging_total NUMERIC;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Reconciling Revenue';
    RAISE NOTICE '========================================';

    SELECT COALESCE(SUM(sales_amount), 0) INTO fact_total FROM warehouse.fact_sales;
    SELECT COALESCE(SUM(sls_sales), 0) INTO staging_total FROM staging.sales_details;

    RAISE NOTICE '  Fact total: %, staging total: %', fact_total, staging_total;

    IF fact_total <> staging_total THEN
        RAISE NOTICE '  ✗ Revenue drift: %.', fact_total - staging_total;
        RAISE EXCEPTION 'Revenue reconciliation FAILED: fact=% staging=%.', fact_total, staging_total;
    ELSE
        RAISE NOTICE '  ✓ Revenue reconciles exactly.';
    END IF;

    RAISE NOTICE '========================================';

END $$;
