/*
===============================================================================
 Script Name : 07_lp_check_orphan_customers.sql
 Description : Every sales line and every demographic row must resolve to a
               known customer in staging.cust_info.
               - sales_details.sls_cust_id -> cust_info.cst_id.
               - loc_a101.cid -> cust_info.cst_key (dash-free keys).
               Mismatched ID domains are reported as warnings, not failures.
===============================================================================
*/

DO $$
DECLARE
    orphan_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
    warn_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Customer Orphans';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO orphan_count
    FROM staging.sales_details AS s
    LEFT JOIN staging.cust_info AS c
        ON c.cst_id = s.sls_cust_id
    WHERE c.cst_id IS NULL;

    IF orphan_count > 0 THEN
        any_failed := TRUE;
        RAISE NOTICE '  ✗ Sales lines with unknown customer: %', orphan_count;
        fail_msg := fail_msg || format('sales orphan customers=%s; ', orphan_count);
    ELSE
        RAISE NOTICE '  ✓ Every sales line has a known customer.';
    END IF;

    SELECT COUNT(*)
    INTO orphan_count
    FROM staging.loc_a101 AS l
    LEFT JOIN staging.cust_info AS c
        ON c.cst_key = l.cid
    WHERE c.cst_key IS NULL;

    IF orphan_count > 0 THEN
        RAISE NOTICE '  … Location rows outside cust_info domain: % (warning only).', orphan_count;
        warn_msg := warn_msg || format('loc outside cust_info=%s; ', orphan_count);
    ELSE
        RAISE NOTICE '  ✓ Every location resolves to cust_info.';
    END IF;

    SELECT COUNT(*)
    INTO orphan_count
    FROM staging.cust_az12 AS a
    LEFT JOIN staging.cust_info AS c
        ON c.cst_key = a.cid
    WHERE c.cst_key IS NULL;

    IF orphan_count > 0 THEN
        RAISE NOTICE '  … Demographic rows outside cust_info domain: % (warning only).', orphan_count;
        warn_msg := warn_msg || format('cust_az12 outside cust_info=%s; ', orphan_count);
    ELSE
        RAISE NOTICE '  ✓ Every demographic row resolves to cust_info.';
    END IF;

    IF warn_msg <> '' THEN
        RAISE NOTICE '  Warnings: %', warn_msg;
    END IF;

    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION 'Customer orphan validation FAILED: %', fail_msg;
    ELSE
        RAISE NOTICE '✓ Customer orphan checks passed.';
    END IF;

END $$;
