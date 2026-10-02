/*
===============================================================================
 Script Name : 11_lp_check_timestamps.sql
 Description : Every staging row carries both load timestamps.
               - updated_at is NOT NULL.
               - loaded_at is NOT NULL.
===============================================================================
*/

DO $$
DECLARE
    ts_rule RECORD;
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Timestamps';
    RAISE NOTICE '========================================';

    FOR ts_rule IN
        SELECT table_name, column_name
        FROM (VALUES
            ('cust_info', 'updated_at'),
            ('cust_info', 'loaded_at'),
            ('prd_info', 'updated_at'),
            ('prd_info', 'loaded_at'),
            ('cust_az12', 'updated_at'),
            ('cust_az12', 'loaded_at'),
            ('loc_a101', 'updated_at'),
            ('loc_a101', 'loaded_at'),
            ('sales_details', 'updated_at'),
            ('sales_details', 'loaded_at'),
            ('px_cat_g1v2', 'updated_at'),
            ('px_cat_g1v2', 'loaded_at')
        ) AS rules(table_name, column_name)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM staging.%I WHERE %I IS NULL',
            ts_rule.table_name,
            ts_rule.column_name
        )
        INTO invalid_count;

        IF invalid_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ %.% NULLs: %', ts_rule.table_name, ts_rule.column_name, invalid_count;
            fail_msg := fail_msg || format(
                '%s.%s NULL; ',
                ts_rule.table_name,
                ts_rule.column_name
            );
        ELSE
            RAISE NOTICE '  ✓ %.% populated.', ts_rule.table_name, ts_rule.column_name;
        END IF;

    END LOOP;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Timestamp validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Staging timestamps populated.';
    END IF;

END $$;
