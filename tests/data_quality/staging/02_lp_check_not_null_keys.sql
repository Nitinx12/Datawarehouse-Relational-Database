/*
===============================================================================
 Script Name : 02_lp_check_not_null_keys.sql
 Description : Merge keys must never be NULL in Staging tables.
               - cust_info.cst_id, prd_info.prd_id, cust_az12.cid,
                 loc_a101.cid are NOT NULL.
               - sales_details.sls_ord_num / sls_prd_key are NOT NULL.
===============================================================================
*/

DO $$
DECLARE
    key_rule RECORD;
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging NOT NULL Keys';
    RAISE NOTICE '========================================';

    FOR key_rule IN
        SELECT * FROM (VALUES
            ('cust_info', 'cst_id'),
            ('prd_info', 'prd_id'),
            ('cust_az12', 'cid'),
            ('loc_a101', 'cid'),
            ('sales_details', 'sls_ord_num'),
            ('sales_details', 'sls_prd_key'),
            ('px_cat_g1v2', 'id')
        ) AS rules(table_name, column_name)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM staging.%I WHERE %I IS NULL',
            key_rule.table_name,
            key_rule.column_name
        )
        INTO invalid_count;

        IF invalid_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ %.% NULLs: %', key_rule.table_name, key_rule.column_name, invalid_count;
            fail_msg := fail_msg || format(
                '%s.%s NULL; ',
                key_rule.table_name,
                key_rule.column_name
            );
        ELSE
            RAISE NOTICE '  ✓ %.% has no NULLs.', key_rule.table_name, key_rule.column_name;
        END IF;

    END LOOP;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'NOT NULL key validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Staging keys contain no NULL values.';
    END IF;

END $$;
