/*
===============================================================================
 Script Name : 08_lp_check_dim_names.sql
 Description : Customer names must be populated in the dimension.
===============================================================================
*/

DO $$
DECLARE
    invalid_count BIGINT;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Dimension Names';
    RAISE NOTICE '========================================';

    SELECT COUNT(*)
    INTO invalid_count
    FROM warehouse.dim_customers
    WHERE first_name IS NULL
        OR last_name IS NULL;

    IF invalid_count > 0 THEN
        RAISE NOTICE '  ✗ Customers missing names: %', invalid_count;
        RAISE EXCEPTION 'Dimension name validation FAILED: % nameless customers.', invalid_count;
    ELSE
        RAISE NOTICE '  ✓ Every customer named.';
    END IF;

    RAISE NOTICE '========================================';

END $$;
