/*
===============================================================================
 Script Name : 04_lp_check_fact_keys.sql
 Description : Every fact row must resolve both dimension keys and carry
               its order number. NULL FKs mean broken dimension coverage.
===============================================================================
*/

DO $$
DECLARE
    fk_rule RECORD;
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Fact Foreign Keys';
    RAISE NOTICE '========================================';

    FOR fk_rule IN
        SELECT * FROM (VALUES
            ('product_key'),
            ('customer_key'),
            ('order_number')
        ) AS rules(column_name)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM warehouse.fact_sales WHERE %I IS NULL',
            fk_rule.column_name
        )
        INTO invalid_count;

        IF invalid_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ fact_sales.% NULLs: %', fk_rule.column_name, invalid_count;
            fail_msg := fail_msg || format('%s NULL=%s; ', fk_rule.column_name, invalid_count);
        ELSE
            RAISE NOTICE '  ✓ fact_sales.% fully resolved.', fk_rule.column_name;
        END IF;

    END LOOP;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Fact key validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Fact keys resolved.';
    END IF;

END $$;
