/*
===============================================================================
 Script Name : 09_lp_check_domains.sql
 Description : Decoded staging columns must only hold their allowed values.
               Anything else means the clean mapping missed a case.
===============================================================================
*/

DO $$
DECLARE
    domain_rule RECORD;
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Value Domains';
    RAISE NOTICE '========================================';

    FOR domain_rule IN
        SELECT * FROM (VALUES
            ('cust_az12', 'gender', ARRAY['Male', 'Female', 'n/a']),
            ('cust_info', 'cst_marital_status', ARRAY['Single', 'Married', 'n/a']),
            ('cust_info', 'cst_gndr', ARRAY['Female', 'Male', 'n/a']),
            ('prd_info', 'prd_line', ARRAY['Mountain', 'Road', 'Other Sales', 'Touring', 'n/a'])
        ) AS rules(table_name, column_name, allowed)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM staging.%I WHERE %I IS NULL OR NOT (%I = ANY ($1))',
            domain_rule.table_name,
            domain_rule.column_name,
            domain_rule.column_name
        )
        INTO invalid_count
        USING domain_rule.allowed;

        IF invalid_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ %.% out-of-domain: %', domain_rule.table_name, domain_rule.column_name, invalid_count;
            fail_msg := fail_msg || format(
                '%s.%s out-of-domain=%s; ',
                domain_rule.table_name,
                domain_rule.column_name,
                invalid_count
            );
        ELSE
            RAISE NOTICE '  ✓ %.% domain clean.', domain_rule.table_name, domain_rule.column_name;
        END IF;

    END LOOP;

    EXECUTE
        'SELECT COUNT(*) FROM staging.loc_a101 WHERE cntry IN (''US'', ''USA'', ''DE'', '''') OR cntry IS NULL'
    INTO invalid_count;

    IF invalid_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ loc_a101.cntry raw codes left: %', invalid_count;
        fail_msg := fail_msg || format('loc_a101 raw country=%s; ', invalid_count);
    ELSE
        RAISE NOTICE '  ✓ loc_a101.cntry fully decoded.';
    END IF;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Domain validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Staging domains clean.';
    END IF;

END $$;
