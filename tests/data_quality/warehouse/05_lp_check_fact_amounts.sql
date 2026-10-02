/*
===============================================================================
 Script Name : 05_lp_check_fact_amounts.sql
 Description : Fact measures must be populated, non-negative and
               consistent: sales = quantity * ABS(price).
===============================================================================
*/

DO $$
DECLARE
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Fact Amounts';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.fact_sales
    WHERE sales_amount IS NULL
        OR quantity IS NULL
        OR price IS NULL;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ NULL measures: %', invalid_count;
        fail_msg := fail_msg || format('NULL measures=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ All measures populated.';
    END IF;

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.fact_sales
    WHERE sales_amount < 0
        OR quantity < 0
        OR price < 0;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Negative measures: %', invalid_count;
        fail_msg := fail_msg || format('negative measures=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ All measures non-negative.';
    END IF;

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.fact_sales
    WHERE sales_amount <> quantity * ABS(price);

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Broken sales math: %', invalid_count;
        fail_msg := fail_msg || format('math mismatch=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ Every line satisfies sales = quantity * ABS(price).';
    END IF;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Fact amount validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ Fact amounts valid.';
    END IF;

END $$;
