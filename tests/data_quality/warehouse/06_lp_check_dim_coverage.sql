/*
===============================================================================
 Script Name : 06_lp_check_dim_coverage.sql
 Description : Dimensions must be fully populated where the mapping is
               complete: product categories and customer country.
===============================================================================
*/

DO $$
DECLARE
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Dimension Coverage';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.dim_products
    WHERE category_id IS NULL
        OR category IS NULL
        OR subcategory IS NULL;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Products missing category: %', invalid_count;
        fail_msg := fail_msg || format('uncategorized products=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ Every product categorized.';
    END IF;

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.dim_customers
    WHERE country IS NULL;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Customers missing country: %', invalid_count;
        fail_msg := fail_msg || format('countryless customers=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ Every customer has a country.';
    END IF;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Dimension coverage validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ Dimension coverage complete.';
    END IF;

END $$;
