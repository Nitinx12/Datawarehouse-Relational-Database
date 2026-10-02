/*
===============================================================================
 Script Name : 03_lp_check_fact_grain.sql
 Description : The fact must hold exactly one row per staging sales line.
               Any difference means fan-out (duplicates) or dropped rows.
===============================================================================
*/

DO $$
DECLARE
    fact_count BIGINT;
    staging_count BIGINT;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Fact Grain';
    RAISE NOTICE '========================================';

    SELECT COUNT(*) INTO fact_count FROM warehouse.fact_sales;
    SELECT COUNT(*) INTO staging_count FROM staging.sales_details;

    RAISE NOTICE '  Fact rows: %, staging rows: %', fact_count, staging_count;

    IF fact_count <> staging_count THEN
        RAISE NOTICE '  ✗ Grain mismatch: % vs %.', fact_count, staging_count;
        RAISE EXCEPTION 'Fact grain validation FAILED: fact=% staging=%.', fact_count, staging_count;
    ELSE
        RAISE NOTICE '  ✓ One fact row per staging line.';
    END IF;

    RAISE NOTICE '========================================';

END $$;
