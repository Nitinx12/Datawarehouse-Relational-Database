/*
===============================================================================
 Script Name : 10_lp_check_date_logic.sql
 Description : Date sanity across Staging.
               - Ship date never before order date (blocking).
               - Birthdates never in the future (blocking).
               - Product end before start is a known source quirk (warning).
===============================================================================
*/

DO $$
DECLARE
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Date Logic';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO invalid_count
    FROM staging.sales_details
    WHERE sls_ship_dt IS NOT NULL
        AND sls_order_dt IS NOT NULL
        AND sls_ship_dt < sls_order_dt;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Ship-before-order lines: %', invalid_count;
        fail_msg := fail_msg || format('ship before order=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ No ship-before-order lines.';
    END IF;

    SELECT COUNT(*)
    INTO invalid_count
    FROM staging.cust_az12
    WHERE birthdate > CURRENT_DATE;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Future birthdates: %', invalid_count;
        fail_msg := fail_msg || format('future birthdates=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ No future birthdates.';
    END IF;

    SELECT COUNT(*)
    INTO invalid_count
    FROM staging.prd_info
    WHERE end_date IS NOT NULL
        AND end_date < start_date;

    IF invalid_count > 0 THEN
        RAISE NOTICE '  … Products ending before start: % (warning only).', invalid_count;
    ELSE
        RAISE NOTICE '  ✓ No products ending before start.';
    END IF;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Date logic validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ Staging date logic passed.';
    END IF;

END $$;
