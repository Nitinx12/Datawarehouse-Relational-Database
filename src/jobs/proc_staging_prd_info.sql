-- ===========================================================================
-- Procedure : staging.load_prd_info
-- Purpose   : Incremental staging load for prd_info.
--             Merges only rows whose (prd_id, prd_key, _loaded_at) triple
--             is not already staged. NULL prd_id rows cannot be merged and
--             are counted separately.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_staging_prd_info.sql
-- Run       : CALL staging.load_prd_info();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.prd_info (
    prd_id TEXT,
    prd_key TEXT,
    prd_nm TEXT,
    prd_cost NUMERIC,
    prd_line TEXT,
    start_date DATE,
    end_date DATE,
    updated_at TIMESTAMP,
    loaded_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_staging_prd_info_prd_id
    ON staging.prd_info (prd_id);

CREATE OR REPLACE PROCEDURE staging.load_prd_info()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
    v_null_keys BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Collect the cleaned batch: trim names, decode the product line,
    -- keep only numeric costs, then apply the incremental filter.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH cleaned AS (
        SELECT
            prd_id,
            TRIM(prd_key) AS prd_key,
            TRIM(prd_nm) AS prd_nm,
            CASE
                WHEN TRIM(prd_cost) ~ '^[0-9]+(\.[0-9]+)?$' THEN TRIM(prd_cost) :: NUMERIC
                ELSE NULL
            END AS prd_cost,
            CASE
                WHEN TRIM(prd_line) = 'M' THEN 'Mountain'
                WHEN TRIM(prd_line) = 'R' THEN 'Road'
                WHEN TRIM(prd_line) = 'S' THEN 'Standard'
                WHEN TRIM(prd_line) = 'T' THEN 'Touring'
                ELSE 'n/a'
            END AS prd_line,
            prd_start_dt :: DATE AS start_date,
            prd_end_dt :: DATE AS end_date,
            updated_at :: TIMESTAMP AS updated_at,
            _loaded_at :: TIMESTAMP AS loaded_at
        FROM (
            SELECT
                prd_id,
                prd_key,
                prd_nm,
                prd_cost,
                prd_line,
                prd_start_dt,
                prd_end_dt,
                updated_at,
                _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY prd_id
                    ORDER BY
                        prd_start_dt,
                        updated_at,
                        _loaded_at
                ) AS rnk
            FROM source.prd_info
        ) AS ranked
        WHERE ranked.rnk = 1
    )

    SELECT
        cleaned.prd_id,
        cleaned.prd_key,
        cleaned.prd_nm,
        cleaned.prd_cost,
        cleaned.prd_line,
        cleaned.start_date,
        cleaned.end_date,
        cleaned.updated_at,
        cleaned.loaded_at
    FROM cleaned
    WHERE cleaned.prd_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM staging.prd_info AS staged
            WHERE staged.prd_id = cleaned.prd_id
                AND staged.prd_key IS NOT DISTINCT FROM cleaned.prd_key
                AND staged.loaded_at IS NOT DISTINCT FROM cleaned.loaded_at
        );

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    SELECT COUNT(*)
    INTO v_null_keys
    FROM source.prd_info
    WHERE prd_id IS NULL;

    -- =======================================================================
    -- Merge the batch, splitting inserted versus updated rows with xmax.
    -- =======================================================================
    WITH upsert AS (
        INSERT INTO staging.prd_info (
            prd_id,
            prd_key,
            prd_nm,
            prd_cost,
            prd_line,
            start_date,
            end_date,
            updated_at,
            loaded_at
        )
        SELECT
            prd_id,
            prd_key,
            prd_nm,
            prd_cost,
            prd_line,
            start_date,
            end_date,
            updated_at,
            loaded_at
        FROM new_rows
        ON CONFLICT (prd_id) DO UPDATE SET
            prd_key = EXCLUDED.prd_key,
            prd_nm = EXCLUDED.prd_nm,
            prd_cost = EXCLUDED.prd_cost,
            prd_line = EXCLUDED.prd_line,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
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

    RAISE NOTICE 'staging.prd_info: staged=% inserted=% updated=% null-key skipped=%',
        v_rows,
        v_inserted,
        v_updated,
        v_null_keys;
END;
$$;
