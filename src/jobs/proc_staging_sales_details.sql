-- ===========================================================================
-- Procedure : staging.load_sales_details
-- Purpose   : Incremental staging load for sales_details.
--             Dates recomputed to NULL unless valid YYYYMMDD, sales
--             recalculated when missing or mismatched, price derived when
--             invalid. Merges only rows whose
--             (sls_ord_num, sls_prd_key, _loaded_at) triple is not staged.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_staging_sales_details.sql
-- Run       : CALL staging.load_sales_details();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.sales_details (
    sls_ord_num TEXT,
    sls_prd_key TEXT,
    sls_cust_id TEXT,
    sls_order_dt DATE,
    sls_ship_dt DATE,
    sls_due_dt DATE,
    sls_sales NUMERIC,
    sls_quantity NUMERIC,
    sls_price NUMERIC,
    updated_at TIMESTAMP,
    loaded_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_staging_sales_details_ord_prd
    ON staging.sales_details (sls_ord_num, sls_prd_key);

CREATE OR REPLACE PROCEDURE staging.load_sales_details()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
    v_null_keys BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Collect the cleaned batch: cast TEXT dates and numbers with guards,
    -- recalculate sales, derive price, then apply the incremental filter.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH typed AS (
        SELECT
            sls_ord_num,
            sls_prd_key,
            sls_cust_id,
            CASE
                WHEN sls_order_dt ~ '^[0-9]{8}$'
                    AND sls_order_dt <> '00000000'
                    THEN TO_DATE(sls_order_dt, 'YYYYMMDD')
                ELSE NULL
            END AS sls_order_dt,
            CASE
                WHEN sls_ship_dt ~ '^[0-9]{8}$'
                    AND sls_ship_dt <> '00000000'
                    THEN TO_DATE(sls_ship_dt, 'YYYYMMDD')
                ELSE NULL
            END AS sls_ship_dt,
            CASE
                WHEN sls_due_dt ~ '^[0-9]{8}$'
                    AND sls_due_dt <> '00000000'
                    THEN TO_DATE(sls_due_dt, 'YYYYMMDD')
                ELSE NULL
            END AS sls_due_dt,
            CASE
                WHEN sls_sales ~ '^-?[0-9]+(\.[0-9]+)?$' THEN sls_sales :: NUMERIC
                ELSE NULL
            END AS sls_sales,
            CASE
                WHEN sls_quantity ~ '^-?[0-9]+(\.[0-9]+)?$' THEN sls_quantity :: NUMERIC
                ELSE NULL
            END AS sls_quantity,
            CASE
                WHEN sls_price ~ '^-?[0-9]+(\.[0-9]+)?$' THEN sls_price :: NUMERIC
                ELSE NULL
            END AS sls_price,
            updated_at,
            _loaded_at
        FROM source.sales_details
    ),

    cleaned AS (
        SELECT
            sls_ord_num,
            sls_prd_key,
            sls_cust_id,
            sls_order_dt,
            sls_ship_dt,
            sls_due_dt,
            CASE
                WHEN sls_sales IS NULL
                    OR sls_sales <= 0
                    OR sls_sales <> sls_quantity * ABS(sls_price)
                    THEN sls_quantity * ABS(sls_price)
                ELSE sls_sales
            END AS sls_sales,
            sls_quantity,
            sls_price,
            updated_at,
            _loaded_at
        FROM typed
    )

    SELECT
        cleaned.sls_ord_num,
        cleaned.sls_prd_key,
        cleaned.sls_cust_id,
        cleaned.sls_order_dt,
        cleaned.sls_ship_dt,
        cleaned.sls_due_dt,
        cleaned.sls_sales,
        cleaned.sls_quantity,
        CASE
            WHEN cleaned.sls_price IS NULL
                OR cleaned.sls_price <= 0
                THEN cleaned.sls_sales / NULLIF(cleaned.sls_quantity, 0)
            ELSE cleaned.sls_price
        END AS sls_price,
        cleaned.updated_at :: TIMESTAMP AS updated_at,
        cleaned._loaded_at :: TIMESTAMP AS loaded_at
    FROM cleaned
    WHERE cleaned.sls_ord_num IS NOT NULL
        AND cleaned.sls_prd_key IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM staging.sales_details AS staged
            WHERE staged.sls_ord_num = cleaned.sls_ord_num
                AND staged.sls_prd_key = cleaned.sls_prd_key
                AND staged.loaded_at IS NOT DISTINCT FROM cleaned._loaded_at :: TIMESTAMP
        );

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    SELECT COUNT(*)
    INTO v_null_keys
    FROM source.sales_details
    WHERE sls_ord_num IS NULL
        OR sls_prd_key IS NULL;

    -- =======================================================================
    -- Merge the batch, splitting inserted versus updated rows with xmax.
    -- =======================================================================
    WITH upsert AS (
        INSERT INTO staging.sales_details (
            sls_ord_num,
            sls_prd_key,
            sls_cust_id,
            sls_order_dt,
            sls_ship_dt,
            sls_due_dt,
            sls_sales,
            sls_quantity,
            sls_price,
            updated_at,
            loaded_at
        )
        SELECT
            sls_ord_num,
            sls_prd_key,
            sls_cust_id,
            sls_order_dt,
            sls_ship_dt,
            sls_due_dt,
            sls_sales,
            sls_quantity,
            sls_price,
            updated_at,
            loaded_at
        FROM new_rows
        ON CONFLICT (sls_ord_num, sls_prd_key) DO UPDATE SET
            sls_cust_id = EXCLUDED.sls_cust_id,
            sls_order_dt = EXCLUDED.sls_order_dt,
            sls_ship_dt = EXCLUDED.sls_ship_dt,
            sls_due_dt = EXCLUDED.sls_due_dt,
            sls_sales = EXCLUDED.sls_sales,
            sls_quantity = EXCLUDED.sls_quantity,
            sls_price = EXCLUDED.sls_price,
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

    RAISE NOTICE 'staging.sales_details: staged=% inserted=% updated=% null-key skipped=%',
        v_rows,
        v_inserted,
        v_updated,
        v_null_keys;
END;
$$;
