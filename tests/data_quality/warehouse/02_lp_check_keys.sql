/*
===============================================================================
 Script Name : 02_lp_check_keys.sql
 Description : Surrogate and business keys must be NOT NULL and UNIQUE.
               - dim_customers.customer_sk / customer_key.
               - dim_products.product_sk / product_id.
===============================================================================
*/

DO $$
DECLARE
    key_rule RECORD;
    invalid_count BIGINT;
    duplicate_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Warehouse Keys';
    RAISE NOTICE '========================================';

    FOR key_rule IN
        SELECT * FROM (VALUES
            ('dim_customers', 'customer_sk', 'customer_key'),
            ('dim_products', 'product_sk', 'product_id')
        ) AS rules(table_name, surrogate_key, business_key)
    LOOP

        EXECUTE format(
            'SELECT COUNT(*) FROM warehouse.%I WHERE %I IS NULL OR %I IS NULL',
            key_rule.table_name,
            key_rule.surrogate_key,
            key_rule.business_key
        )
        INTO invalid_count;

        IF invalid_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ % NULL keys: %', key_rule.table_name, invalid_count;
            fail_msg := fail_msg || format('%s NULL keys=%s; ', key_rule.table_name, invalid_count);
        ELSE
            RAISE NOTICE '  ✓ % keys contain no NULLs.', key_rule.table_name;
        END IF;

        EXECUTE format(
            'SELECT COUNT(*) FROM (SELECT %I FROM warehouse.%I GROUP BY %I HAVING COUNT(*) > 1) x',
            key_rule.surrogate_key,
            key_rule.table_name,
            key_rule.surrogate_key
        )
        INTO duplicate_count;

        EXECUTE format(
            'SELECT COUNT(*) FROM (SELECT %I FROM warehouse.%I GROUP BY %I HAVING COUNT(*) > 1) x',
            key_rule.business_key,
            key_rule.table_name,
            key_rule.business_key
        )
        INTO invalid_count;

        duplicate_count := duplicate_count + invalid_count;

        IF duplicate_count > 0 THEN
            any_failed := TRUE;
            RAISE NOTICE '  ✗ % duplicate keys: %', key_rule.table_name, duplicate_count;
            fail_msg := fail_msg || format('%s duplicate keys=%s; ', key_rule.table_name, duplicate_count);
        ELSE
            RAISE NOTICE '  ✓ % keys are unique.', key_rule.table_name;
        END IF;

    END LOOP;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Warehouse key validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ All Warehouse keys valid.';
    END IF;

END $$;
