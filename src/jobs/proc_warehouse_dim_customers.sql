-- ===========================================================================
-- Procedure : warehouse.load_dim_customers
-- Purpose   : SCD1 customer dimension from staging.cust_info (master),
--             staging.cust_az12 (demographics) and staging.loc_a101
--             (geography), keyed on the dash-free customer key.
--             New keys are inserted, changed attributes updated in place,
--             unchanged rows untouched. Demographics-only keys outside
--             cust_info are kept with NULL master attributes.
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
    source_system TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE PROCEDURE warehouse.load_dim_customers()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Combine the three staging sources, demographics winning on gender.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH combined AS (
        SELECT
            COALESCE(info.cst_key, demo.cid, geo.cid) AS customer_key,
            info.cst_id,
            info.cst_first_name AS first_name,
            info.cst_last_name AS last_name,
            info.cst_marital_status AS marital_status,
            COALESCE(
                NULLIF(info.cst_gndr, 'n/a'),
                NULLIF(demo.gender, 'n/a'),
                'n/a'
            ) AS gender,
            demo.birthdate,
            COALESCE(geo.cntry, 'n/a') AS country,
            info.create_date AS create_date,
            CASE
                WHEN info.cst_key IS NOT NULL
                    AND (demo.cid IS NOT NULL OR geo.cid IS NOT NULL)
                    THEN 'multiple'
                WHEN info.cst_key IS NOT NULL THEN 'cust_info'
                WHEN demo.cid IS NOT NULL THEN 'cust_az12'
                ELSE 'loc_a101'
            END AS source_system
        FROM staging.cust_info AS info
        FULL OUTER JOIN staging.cust_az12 AS demo
            ON demo.cid = info.cst_key
        FULL OUTER JOIN staging.loc_a101 AS geo
            ON geo.cid = COALESCE(info.cst_key, demo.cid)
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
        combined.create_date,
        combined.source_system
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
            create_date,
            source_system
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
            create_date,
            source_system
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
            source_system = EXCLUDED.source_system,
            updated_at = NOW()
        WHERE warehouse.dim_customers.cst_id IS DISTINCT FROM EXCLUDED.cst_id
            OR warehouse.dim_customers.first_name IS DISTINCT FROM EXCLUDED.first_name
            OR warehouse.dim_customers.last_name IS DISTINCT FROM EXCLUDED.last_name
            OR warehouse.dim_customers.marital_status IS DISTINCT FROM EXCLUDED.marital_status
            OR warehouse.dim_customers.gender IS DISTINCT FROM EXCLUDED.gender
            OR warehouse.dim_customers.birthdate IS DISTINCT FROM EXCLUDED.birthdate
            OR warehouse.dim_customers.country IS DISTINCT FROM EXCLUDED.country
            OR warehouse.dim_customers.create_date IS DISTINCT FROM EXCLUDED.create_date
            OR warehouse.dim_customers.source_system IS DISTINCT FROM EXCLUDED.source_system
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
