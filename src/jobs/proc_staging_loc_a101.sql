-- ===========================================================================
-- Procedure : staging.load_loc_a101
-- Purpose   : Incremental staging load for LOC_A101.
--             Merges only rows whose (cid, cntry, _loaded_at) triple
--             is not already staged.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_staging_loc_a101.sql
-- Run       : CALL staging.load_loc_a101();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.loc_a101 (
    cid TEXT,
    cntry TEXT,
    updated_at TIMESTAMP,
    loaded_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_staging_loc_a101_cid
    ON staging.loc_a101 (cid);

CREATE OR REPLACE PROCEDURE staging.load_loc_a101()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
    v_null_keys BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Collect the cleaned batch: dash-free cid, decoded country, then the
    -- incremental filter.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH cleaned AS (
        SELECT
            REPLACE("CID", '-', '') AS cid,
            CASE
                WHEN TRIM("CNTRY") = 'DE' THEN 'Germany'
                WHEN TRIM("CNTRY") IN ('US', 'USA') THEN 'United States'
                WHEN TRIM("CNTRY") = '' OR "CNTRY" IS NULL THEN 'n/a'
                ELSE TRIM("CNTRY")
            END AS cntry,
            updated_at :: TIMESTAMP AS updated_at,
            _loaded_at :: TIMESTAMP AS loaded_at
        FROM source."LOC_A101"
    )

    SELECT
        cleaned.cid,
        cleaned.cntry,
        cleaned.updated_at,
        cleaned.loaded_at
    FROM cleaned
    WHERE cleaned.cid IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM staging.loc_a101 AS staged
            WHERE staged.cid = cleaned.cid
                AND staged.cntry IS NOT DISTINCT FROM cleaned.cntry
                AND staged.loaded_at IS NOT DISTINCT FROM cleaned.loaded_at
        );

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    SELECT COUNT(*)
    INTO v_null_keys
    FROM source."LOC_A101"
    WHERE "CID" IS NULL;

    -- =======================================================================
    -- Merge the batch, splitting inserted versus updated rows with xmax.
    -- =======================================================================
    WITH upsert AS (
        INSERT INTO staging.loc_a101 (
            cid,
            cntry,
            updated_at,
            loaded_at
        )
        SELECT
            cid,
            cntry,
            updated_at,
            loaded_at
        FROM new_rows
        ON CONFLICT (cid) DO UPDATE SET
            cntry = EXCLUDED.cntry,
            updated_at = EXCLUDED.updated_at,
            loaded_at = EXCLUDED.loaded_at
        RETURNING (xmax = 0) AS inserted
    )

    SELECT
        count(*) FILTER (WHERE inserted),
        count(*) FILTER (WHERE NOT inserted)
    INTO
        v_inserted,
        v_updated
    FROM upsert;

    RAISE NOTICE 'staging.loc_a101: staged=% inserted=% updated=% null-key skipped=%',
        v_rows,
        v_inserted,
        v_updated,
        v_null_keys;
END;
$$;
