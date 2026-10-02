/*
===============================================================================
 Script Name : 07_lp_check_dim_domains.sql
 Description : Decoded dimension columns must only hold allowed values.
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
    RAISE NOTICE 'Checking Dimension Domains';
    RAISE NOTICE '========================================';

    FOR domain_rule IN
        SELECT * FROM (VALUES
            ('dim_customers', 'gender', ARRAY['Male', 'Female', 'n/a']),
            ('dim_customers', 'marital_status', ARRAY['Single', 'Married', 'n/a']),
            ('dim_products', 'product_line', ARRAY['Mountain', 'Road', 'Other Sales', 'Touring', 'n/a'])
        ) AS rules(table_name, column_name, allowed)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM warehouse.%I WHERE %I IS NULL OR NOT (%I = ANY ($1))',
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

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Dimension domain validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Dimension domains clean.';
    END IF;

END $$;
