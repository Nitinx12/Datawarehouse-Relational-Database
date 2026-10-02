/*
===============================================================================
 Script Name : 09_lp_check_order_dates.sql
 Description : Fact order dates must exist, never be in the future, and
               ship never before order. Null order dates (invalid source
               strings quarantined at load) are reported as warnings.
===============================================================================
*/

DO $$
DECLARE
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Fact Order Dates';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.fact_sales
    WHERE order_date IS NULL;

    IF invalid_count > 0 THEN
        RAISE NOTICE '  … NULL order dates: % (warning only).', invalid_count;
    ELSE
        RAISE NOTICE '  ✓ Every line has an order date.';
    END IF;

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.fact_sales
    WHERE order_date > CURRENT_DATE;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Future order dates: %', invalid_count;
        fail_msg := fail_msg || format('future orders=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ No future order dates.';
    END IF;

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.fact_sales
    WHERE shipping_date IS NOT NULL
        AND order_date IS NOT NULL
        AND shipping_date < order_date;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Ship-before-order lines: %', invalid_count;
        fail_msg := fail_msg || format('ship before order=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ No ship-before-order lines.';
    END IF;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Order date validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ Fact order dates valid.';
    END IF;

END $$;
