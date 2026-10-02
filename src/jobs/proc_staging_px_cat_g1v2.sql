-- ===========================================================================
-- Procedure : staging.load_px_cat_g1v2
-- Purpose   : Full-refresh staging load for PX_CAT_G1V2.
--             Tiny reference table, so it truncates and reloads fully
--             instead of incremental merge.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_staging_px_cat_g1v2.sql
-- Run       : CALL staging.load_px_cat_g1v2();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.px_cat_g1v2 (
    id TEXT,
    cat TEXT,
    subcat TEXT,
    maintenance TEXT,
    updated_at TIMESTAMP,
    loaded_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_staging_px_cat_g1v2_id
    ON staging.px_cat_g1v2 (id);

CREATE OR REPLACE PROCEDURE staging.load_px_cat_g1v2()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Full refresh: truncate, then reload the cleaned reference rows.
    -- =======================================================================
    TRUNCATE TABLE staging.px_cat_g1v2;

    INSERT INTO staging.px_cat_g1v2 (
        id,
        cat,
        subcat,
        maintenance,
        updated_at,
        loaded_at
    )
    WITH cleaned AS (
        SELECT
            id,
            TRIM("CAT") AS cat,
            TRIM("SUBCAT") AS subcat,
            TRIM("MAINTENANCE") AS maintenance,
            updated_at :: TIMESTAMP AS updated_at,
            _loaded_at :: TIMESTAMP AS loaded_at
        FROM source."PX_CAT_G1V2"
    )

    SELECT
        cleaned.id,
        cleaned.cat,
        cleaned.subcat,
        cleaned.maintenance,
        cleaned.updated_at,
        cleaned.loaded_at
    FROM cleaned
    WHERE cleaned.id IS NOT NULL;

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    RAISE NOTICE 'staging.px_cat_g1v2: reloaded=% rows', v_rows;
END;
$$;
