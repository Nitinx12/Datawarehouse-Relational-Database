/*
===============================================================================
 Script Name : 04_lp_check_no_negatives.sql
 Description : Money and quantity measures must never be negative.
               - sales_details.sls_sales / sls_quantity / sls_price >= 0.
               - prd_info.prd_cost >= 0.
===============================================================================
*/

DO $$
DECLARE
    num_rule RECORD;
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Non-Negative Measures';
    RAISE NOTICE '========================================';

    FOR num_rule IN
        SELECT * FROM (VALUES
            ('sales_details', 'sls_sales'),
            ('sales_details', 'sls_quantity'),
            ('sales_details', 'sls_price'),
            ('prd_info', 'prd_cost')
        ) AS rules(table_name, column_name)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM staging.%I WHERE %I IS NOT NULL AND %I < 0',
            num_rule.table_name,
            num_rule.column_name,
            num_rule.column_name
        )
        INTO invalid_count;

        IF invalid_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ %.% negatives: %', num_rule.table_name, num_rule.column_name, invalid_count;
            fail_msg := fail_msg || format(
                '%s.%s negative=%s; ',
                num_rule.table_name,
                num_rule.column_name,
                invalid_count
            );
        ELSE
            RAISE NOTICE '  ✓ %.% has no negatives.', num_rule.table_name, num_rule.column_name;
        END IF;

    END LOOP;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Non-negative validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Staging measures are non-negative.';
    END IF;

END $$;
