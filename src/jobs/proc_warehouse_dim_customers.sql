-- ===========================================================================
-- Procedure : warehouse.load_dim_customers
-- Purpose   : SCD1 customer dimension following team grain and rules:
--             cust_info master with LEFT JOINs to demographics and
--             geography, CRM gender first with ERP fallback.
--             Stable surrogate kept for incremental merge.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_warehouse_dim_customers.sql
-- Run       : CALL warehouse.load_dim_customers();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.dim_customers (
    customer_sk BIGSERIAL PRIMARY KEY,
    customer_key TEXT UNIQUE NOT NULL,
    cst_id TEXT,
    first_name TEXT,
    last_name TEXT,
    marital_status TEXT,
    gender TEXT,
    birthdate DATE,
    country TEXT,
    create_date DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE warehouse.dim_customers DROP COLUMN IF EXISTS source_system;

CREATE OR REPLACE PROCEDURE warehouse.load_dim_customers()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Combine master with demographics and geography, CRM gender first.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH combined AS (
        SELECT
            info.cst_key AS customer_key,
            info.cst_id,
            info.cst_first_name AS first_name,
            info.cst_last_name AS last_name,
            info.cst_marital_status AS marital_status,
            CASE
                WHEN info.cst_gndr != 'n/a' THEN info.cst_gndr
                ELSE COALESCE(demo.gender, 'n/a')
            END AS gender,
            demo.birthdate,
            geo.cntry AS country,
            info.create_date AS create_date
        FROM staging.cust_info AS info
        LEFT JOIN staging.cust_az12 AS demo
            ON demo.cid = info.cst_key
        LEFT JOIN staging.loc_a101 AS geo
            ON geo.cid = info.cst_key
    )

    SELECT
        combined.customer_key,
        combined.cst_id,
        combined.first_name,
        combined.last_name,
        combined.marital_status,
        combined.gender,
        combined.birthdate,
        combined.country,
        combined.create_date
    FROM combined
    WHERE combined.customer_key IS NOT NULL;

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    -- =======================================================================
    -- Merge with change detection: only truly changed rows are updated.
    -- =======================================================================
    WITH upsert AS (
        INSERT INTO warehouse.dim_customers (
            customer_key,
            cst_id,
            first_name,
            last_name,
            marital_status,
            gender,
            birthdate,
            country,
            create_date
        )
        SELECT
            customer_key,
            cst_id,
            first_name,
            last_name,
            marital_status,
            gender,
            birthdate,
            country,
            create_date
        FROM new_rows
        ON CONFLICT (customer_key) DO UPDATE SET
            cst_id = EXCLUDED.cst_id,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            marital_status = EXCLUDED.marital_status,
            gender = EXCLUDED.gender,
            birthdate = EXCLUDED.birthdate,
            country = EXCLUDED.country,
            create_date = EXCLUDED.create_date,
            updated_at = NOW()
        WHERE warehouse.dim_customers.cst_id IS DISTINCT FROM EXCLUDED.cst_id
            OR warehouse.dim_customers.first_name IS DISTINCT FROM EXCLUDED.first_name
            OR warehouse.dim_customers.last_name IS DISTINCT FROM EXCLUDED.last_name
            OR warehouse.dim_customers.marital_status IS DISTINCT FROM EXCLUDED.marital_status
            OR warehouse.dim_customers.gender IS DISTINCT FROM EXCLUDED.gender
            OR warehouse.dim_customers.birthdate IS DISTINCT FROM EXCLUDED.birthdate
            OR warehouse.dim_customers.country IS DISTINCT FROM EXCLUDED.country
            OR warehouse.dim_customers.create_date IS DISTINCT FROM EXCLUDED.create_date
        RETURNING (xmax = 0) AS inserted
    )

    SELECT
        count(*) FILTER (WHERE inserted),
        count(*) FILTER (WHERE NOT inserted)
    INTO
        v_inserted,
        v_updated
    FROM upsert;

    RAISE NOTICE 'warehouse.dim_customers: combined=% inserted=% updated=%',
        v_rows,
        v_inserted,
        v_updated;
END;
$$;
