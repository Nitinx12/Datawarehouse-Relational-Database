/*
===============================================================================
 Script Name : 03_lp_check_not_null_business.sql
 Description : Business columns that must always be populated.
               NULLs here mean upstream dirt the clean logic could not fix.
===============================================================================
*/

DO $$
DECLARE
    col_rule RECORD;
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging NOT NULL Business Columns';
    RAISE NOTICE '========================================';

    FOR col_rule IN
        SELECT * FROM (VALUES
            ('cust_info', 'cst_first_name'),
            ('cust_info', 'cst_last_name'),
            ('cust_info', 'cst_key'),
            ('prd_info', 'prd_nm'),
            ('cust_az12', 'gender'),
            ('loc_a101', 'cntry'),
            ('sales_details', 'sls_sales'),
            ('sales_details', 'sls_quantity'),
            ('sales_details', 'sls_price')
        ) AS rules(table_name, column_name)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM staging.%I WHERE %I IS NULL',
            col_rule.table_name,
            col_rule.column_name
        )
        INTO invalid_count;

        IF invalid_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ %.% NULLs: %', col_rule.table_name, col_rule.column_name, invalid_count;
            fail_msg := fail_msg || format(
                '%s.%s NULL=%s; ',
                col_rule.table_name,
                col_rule.column_name,
                invalid_count
            );
        ELSE
            RAISE NOTICE '  ✓ %.% has no NULLs.', col_rule.table_name, col_rule.column_name;
        END IF;

    END LOOP;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'NOT NULL business validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Staging business columns populated.';
    END IF;

END $$;
