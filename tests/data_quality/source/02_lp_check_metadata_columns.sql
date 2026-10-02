/*
===============================================================================
 Script Name : 02_lp_check_metadata_columns.sql
 Description : Validate timestamp metadata columns in Source tables.
               - updated_at exists and is NOT NULL.
               - _loaded_at exists and is NOT NULL.
===============================================================================
*/

DO $$
DECLARE
    tbl RECORD;
    ts_col TEXT;
    invalid_count BIGINT;
    any_failed BOOLEAN := FALSE;
    fail_msg TEXT := '';
BEGIN

    RAISE NOTICE '========================================';
    RAISE NOTICE 'Checking Source Timestamp Columns';
    RAISE NOTICE '========================================';

    FOR tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'source'
          AND table_type = 'BASE TABLE'
          AND table_name <> 'etl_logs'
          AND table_name NOT LIKE '%__stg'
        ORDER BY table_name
    LOOP

        RAISE NOTICE '';
        RAISE NOTICE 'Table: %', tbl.table_name;

        FOREACH ts_col IN ARRAY ARRAY[
            'updated_at',
            '_loaded_at'
        ]
        LOOP

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='source'
                  AND table_name=tbl.table_name
                  AND column_name=ts_col
            ) THEN

                RAISE NOTICE '  ✓ Column % exists.', ts_col;

                EXECUTE format(
                    'SELECT COUNT(*) FROM source.%I WHERE %I IS NULL',
                    tbl.table_name,
                    ts_col
                )
                INTO invalid_count;

                IF invalid_count > 0 THEN

                    any_failed := TRUE;

                    RAISE NOTICE
                        '  ✗ % NULLs: %',
                        ts_col,
                        invalid_count;

                    fail_msg := fail_msg || format(
                        '%s %s NULL; ',
                        tbl.table_name,
                        ts_col
                    );

                ELSE

                    RAISE NOTICE
                        '  ✓ % passed.',
                        ts_col;

                END IF;

            ELSE

                any_failed := TRUE;

                RAISE NOTICE '  ✗ Missing column: %', ts_col;

                fail_msg := fail_msg || format(
                    '%s missing %s; ',
                    tbl.table_name,
                    ts_col
                );

            END IF;

        END LOOP;

    END LOOP;

    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Timestamp Validation Complete';
    RAISE NOTICE '========================================';

    IF any_failed THEN
        RAISE EXCEPTION
            'Timestamp validation FAILED: %',
            fail_msg;
    ELSE
        RAISE NOTICE
            '✓ All Source timestamp checks passed.';
    END IF;

END $$;
