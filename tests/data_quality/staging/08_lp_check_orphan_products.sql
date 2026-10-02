/*
===============================================================================
 Script Name : 08_lp_check_orphan_products.sql
 Description : Every sales line should resolve to staging.prd_info.
               Reported as a warning (key domain mismatch under mapping),
               not a blocking failure.
===============================================================================
*/

DO $$
DECLARE
    orphan_count BIGINT;
    total_count BIGINT;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Product Orphans';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO total_count
    FROM staging.sales_details;

    SELECT COUNT(*)
    INTO orphan_count
    FROM staging.sales_details AS s
    LEFT JOIN staging.prd_info AS p
        ON p.prd_key = s.sls_prd_key
    WHERE p.prd_key IS NULL;

    RAISE NOTICE '  Sales lines: %, orphans: %', total_count, orphan_count;

    IF orphan_count > 0 THEN
        RAISE NOTICE '  … % of sales lines have no prd_info match (warning only).',
            round(orphan_count * 100.0 / greatest(total_count, 1), 2);
    ELSE
        RAISE NOTICE '  ✓ Every sales line has a known product.';
    END IF;

    RAISE NOTICE '========================================';

END $$;
