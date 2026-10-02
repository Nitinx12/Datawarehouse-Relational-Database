/*
===============================================================================
 Script Name : 05_lp_check_sales_math.sql
 Description : Every sales line must satisfy sales = quantity * ABS(price).
               Any mismatch means the clean recalculation missed a case.
===============================================================================
*/

DO $$
DECLARE
    invalid_count BIGINT;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Sales Math';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO invalid_count
    FROM staging.sales_details
    WHERE sls_sales IS NULL
        OR sls_quantity IS NULL
        OR sls_price IS NULL
        OR sls_quantity <= 0
        OR sls_sales <> sls_quantity * ABS(sls_price);

    IF invalid_count > 0 THEN
        RAISE NOTICE '  ✗ Broken sales lines: %', invalid_count;
        RAISE EXCEPTION 'Sales math validation FAILED: % broken lines.', invalid_count;
    ELSE
        RAISE NOTICE '  ✓ Every line satisfies sales = quantity * ABS(price).';
    END IF;

    RAISE NOTICE '========================================';

END $$;
