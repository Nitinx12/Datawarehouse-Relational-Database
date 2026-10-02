-- ===========================================================================
-- Procedure : staging.load_cust_az12
-- Purpose   : Incremental staging load for CUST_AZ12.
--             Merges only rows whose (cid, birthdate, _loaded_at) triple
--             is not already staged. Birthdates that are not real calendar
--             dates load as NULL instead of aborting the batch.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_staging_cust_az12.sql
-- Run       : CALL staging.load_cust_az12();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.cust_az12 (
    cid TEXT,
    birthdate DATE,
    gender TEXT,
    updated_at TIMESTAMP,
    loaded_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_staging_cust_az12_cid
    ON staging.cust_az12 (cid);

CREATE OR REPLACE PROCEDURE staging.load_cust_az12()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
    v_null_keys BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Collect the cleaned batch: dash-free cid, validated birthdate,
    -- decoded gender, then the incremental filter.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH cleaned AS (
        SELECT
            UPPER(TRIM(REPLACE("CID", '-', ''))) AS cid,
            CASE
                WHEN "BDATE" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                    AND SUBSTRING("BDATE" FROM 6 FOR 2) :: INT BETWEEN 1 AND 12
                    AND SUBSTRING("BDATE" FROM 9 FOR 2) :: INT BETWEEN 1 AND 31
                    AND (
                        SUBSTRING("BDATE" FROM 6 FOR 2) NOT IN ('02', '04', '06', '09', '11')
                        OR SUBSTRING("BDATE" FROM 9 FOR 2) :: INT <= 30
                    )
                    AND (
                        SUBSTRING("BDATE" FROM 6 FOR 2) <> '02'
                        OR SUBSTRING("BDATE" FROM 9 FOR 2) :: INT <= 28
                        OR (
                            SUBSTRING("BDATE" FROM 9 FOR 2) :: INT = 29
                            AND SUBSTRING("BDATE" FROM 1 FOR 4) :: INT % 4 = 0
                            AND (
                                SUBSTRING("BDATE" FROM 1 FOR 4) :: INT % 100 <> 0
                                OR SUBSTRING("BDATE" FROM 1 FOR 4) :: INT % 400 = 0
                            )
                        )
                    )
                    THEN "BDATE" :: DATE
                ELSE NULL
            END AS birthdate,
            CASE
                WHEN UPPER(TRIM("GEN")) IN ('M', 'MALE') THEN 'Male'
                WHEN UPPER(TRIM("GEN")) IN ('F', 'FEMALE') THEN 'Female'
                ELSE 'n/a'
            END AS gender,
            updated_at :: TIMESTAMP AS updated_at,
            _loaded_at :: TIMESTAMP AS loaded_at
        FROM (
            SELECT
                "CID",
                "BDATE",
                "GEN",
                updated_at,
                _loaded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY UPPER(TRIM(REPLACE("CID", '-', '')))
                    ORDER BY
                        updated_at,
                        _loaded_at
                ) AS rnk
            FROM source."CUST_AZ12"
        ) AS ranked
        WHERE ranked.rnk = 1
    )

    SELECT
        cleaned.cid,
        cleaned.birthdate,
        cleaned.gender,
        cleaned.updated_at,
        cleaned.loaded_at
    FROM cleaned
    WHERE cleaned.cid IS NOT NULL
        AND cleaned.cid <> ''
        AND NOT EXISTS (
            SELECT 1
            FROM staging.cust_az12 AS staged
            WHERE staged.cid = cleaned.cid
                AND staged.birthdate IS NOT DISTINCT FROM cleaned.birthdate
                AND staged.loaded_at IS NOT DISTINCT FROM cleaned.loaded_at
        );

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    SELECT COUNT(*)
    INTO v_null_keys
    FROM source."CUST_AZ12"
    WHERE "CID" IS NULL;

    -- =======================================================================
    -- Merge the batch, splitting inserted versus updated rows with xmax.
    -- =======================================================================
    WITH upsert AS (
        INSERT INTO staging.cust_az12 (
            cid,
            birthdate,
            gender,
            updated_at,
            loaded_at
        )
        SELECT
            cid,
            birthdate,
            gender,
            updated_at,
            loaded_at
        FROM new_rows
        ON CONFLICT (cid) DO UPDATE SET
            birthdate = EXCLUDED.birthdate,
            gender = EXCLUDED.gender,
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

    RAISE NOTICE 'staging.cust_az12: staged=% inserted=% updated=% null-key skipped=%',
        v_rows,
        v_inserted,
        v_updated,
        v_null_keys;
END;
$$;
