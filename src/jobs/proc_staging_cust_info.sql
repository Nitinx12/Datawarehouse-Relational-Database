-- ===========================================================================
-- Procedure : staging.load_cust_info
-- Purpose   : Incremental staging load for cust_info.
--             Merges only rows whose (cst_id, cst_key, _loaded_at) triple
--             is not already staged. NULL cst_id rows cannot be merged and
--             are counted separately.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_staging_cust_info.sql
-- Run       : CALL staging.load_cust_info();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.cust_info (
    cst_id TEXT,
    cst_key TEXT,
    cst_first_name TEXT,
    cst_last_name TEXT,
    cst_marital_status TEXT,
    cst_gndr TEXT,
    create_date DATE,
    updated_at TIMESTAMP,
    loaded_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_staging_cust_info_cst_id
    ON staging.cust_info (cst_id);

CREATE OR REPLACE PROCEDURE staging.load_cust_info()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
    v_null_keys BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Collect the cleaned batch: user clean logic plus incremental filter.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH cleaned AS (
        SELECT
            cst_id,
            cst_key,
            COALESCE(NULLIF(TRIM(cst_firstname), ''), 'Unknown') AS cst_first_name,
            COALESCE(NULLIF(TRIM(cst_lastname), ''), 'Unknown') AS cst_last_name,
            CASE
                WHEN UPPER(TRIM(cst_marital_status)) = 'S' THEN 'Single'
                WHEN UPPER(TRIM(cst_marital_status)) = 'M' THEN 'Married'
                ELSE 'n/a'
            END AS cst_marital_status,
            CASE
                WHEN UPPER(TRIM(cst_gndr)) = 'F' THEN 'Female'
                WHEN UPPER(TRIM(cst_gndr)) = 'M' THEN 'Male'
                ELSE 'n/a'
            END AS cst_gndr,
            cst_create_date :: DATE AS create_date,
            updated_at :: TIMESTAMP AS updated_at,
            _loaded_at :: TIMESTAMP AS loaded_at
        FROM (
            SELECT
                cst_id,
                cst_key,
                cst_firstname,
                cst_lastname,
                cst_marital_status,
                cst_gndr,
                cst_create_date,
                updated_at,
                _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY cst_id
                    ORDER BY
                        cst_create_date DESC,
                        updated_at DESC,
                        _loaded_at DESC
                ) AS rnk
            FROM source.cust_info
        ) AS ranked
        WHERE ranked.rnk = 1
    )

    SELECT
        cleaned.cst_id,
        cleaned.cst_key,
        cleaned.cst_first_name,
        cleaned.cst_last_name,
        cleaned.cst_marital_status,
        cleaned.cst_gndr,
        cleaned.create_date,
        cleaned.updated_at,
        cleaned.loaded_at
    FROM cleaned
    WHERE cleaned.cst_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM staging.cust_info AS staged
            WHERE staged.cst_id = cleaned.cst_id
                AND staged.cst_key IS NOT DISTINCT FROM cleaned.cst_key
                AND staged.loaded_at IS NOT DISTINCT FROM cleaned.loaded_at
        );

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    SELECT COUNT(*)
    INTO v_null_keys
    FROM source.cust_info
    WHERE cst_id IS NULL;

    -- =======================================================================
    -- Merge the batch, splitting inserted versus updated rows with xmax.
    -- =======================================================================
    WITH upsert AS (
        INSERT INTO staging.cust_info (
            cst_id,
            cst_key,
            cst_first_name,
            cst_last_name,
            cst_marital_status,
            cst_gndr,
            create_date,
            updated_at,
            loaded_at
        )
        SELECT
            cst_id,
            cst_key,
            cst_first_name,
            cst_last_name,
            cst_marital_status,
            cst_gndr,
            create_date,
            updated_at,
            loaded_at
        FROM new_rows
        ON CONFLICT (cst_id) DO UPDATE SET
            cst_key = EXCLUDED.cst_key,
            cst_first_name = EXCLUDED.cst_first_name,
            cst_last_name = EXCLUDED.cst_last_name,
            cst_marital_status = EXCLUDED.cst_marital_status,
            cst_gndr = EXCLUDED.cst_gndr,
            create_date = EXCLUDED.create_date,
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

    RAISE NOTICE 'staging.cust_info: staged=% inserted=% updated=% null-key skipped=%',
        v_rows,
        v_inserted,
        v_updated,
        v_null_keys;
END;
$$;
