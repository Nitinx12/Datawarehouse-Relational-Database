/*
===============================================================================
 Script Name : 01_lp_check_staging_tables.sql
 Description : Check every table in the Staging schema.
               - Verify table exists.
               - Count rows.
               - Raise an exception if any table is empty.
===============================================================================
*/

DO $$
DECLARE
    tbl RECORD;
    row_count BIGINT;
    any_empty BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Staging Schema';
    RAISE NOTICE '========================================';

    FOR tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'staging'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    LOOP

        RAISE NOTICE '';
        RAISE NOTICE 'Table: %', tbl.table_name;

        EXECUTE format(
            'SELECT COUNT(*) FROM staging.%I',
            tbl.table_name
        )
        INTO row_count;

        RAISE NOTICE '  Rows: %', row_count;

        IF row_count = 0 THEN
            any_empty := TRUE;

            RAISE NOTICE '  ✗ Table is empty.';

            fail_msg := fail_msg || format(
                '%s (0 rows); ',
                tbl.table_name
            );
        ELSE
            RAISE NOTICE '  ✓ Table loaded successfully.';
        END IF;

    END LOOP;

    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Staging Schema Check Complete';
    RAISE NOTICE '========================================';

    IF any_empty THEN
        RAISE EXCEPTION
            'Staging validation FAILED: %',
            fail_msg;
    ELSE
        RAISE NOTICE
            '✓ All Staging tables contain data.';
    END IF;

END $$;
