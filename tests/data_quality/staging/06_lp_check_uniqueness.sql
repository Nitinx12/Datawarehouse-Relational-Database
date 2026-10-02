/*
===============================================================================
 Script Name : 06_lp_check_uniqueness.sql
 Description : Merge keys must be unique inside each Staging table.
               sales_details grain is (sls_ord_num, sls_prd_key).
===============================================================================
*/

DO $$
DECLARE
    key_rule RECORD;
    duplicate_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Key Uniqueness';
    RAISE NOTICE '========================================';

    FOR key_rule IN
        SELECT * FROM (VALUES
            ('cust_info', 'cst_id', NULL),
            ('prd_info', 'prd_id', NULL),
            ('cust_az12', 'cid', NULL),
            ('loc_a101', 'cid', NULL),
            ('px_cat_g1v2', 'id', NULL),
            ('sales_details', 'sls_ord_num', 'sls_prd_key')
        ) AS rules(table_name, key_one, key_two)
    LOOP

        IF key_rule.key_two IS NULL THEN
            EXECUTE format(
                'SELECT COUNT(*) FROM (SELECT %I FROM staging.%I GROUP BY %I HAVING COUNT(*) > 1) x',
                key_rule.key_one,
                key_rule.table_name,
                key_rule.key_one
            )
            INTO duplicate_count;
        ELSE
            EXECUTE format(
                'SELECT COUNT(*) FROM (SELECT %I, %I FROM staging.%I GROUP BY %I, %I HAVING COUNT(*) > 1) x',
                key_rule.key_one,
                key_rule.key_two,
                key_rule.table_name,
                key_rule.key_one,
                key_rule.key_two
            )
            INTO duplicate_count;
        END IF;

        IF duplicate_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ % duplicate key groups: %', key_rule.table_name, duplicate_count;
            fail_msg := fail_msg || format(
                '%s duplicate keys=%s; ',
                key_rule.table_name,
                duplicate_count
            );
        ELSE
            RAISE NOTICE '  ✓ % keys are unique.', key_rule.table_name;
        END IF;

    END LOOP;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Uniqueness validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Staging keys are unique.';
    END IF;

END $$;
