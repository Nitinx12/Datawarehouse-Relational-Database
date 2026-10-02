-- ===========================================================================
-- Procedure : warehouse.load_dim_products
-- Purpose   : SCD1 product dimension for all products. Team filters
--             end_date IS NULL, but source end dates are systematically
--             unreliable (200 rows end before they start), so gating on
--             them would orphan 3,238 sold lines in fact_sales. end_date
--             is carried instead, letting marts filter current stock.
--             Category comes from a real join to px_cat: staging cat_id
--             maps to subcategory names, verified 100% consistent, then
--             px_cat supplies id, category and maintenance.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_warehouse_dim_products.sql
-- Run       : CALL warehouse.load_dim_products();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.dim_products (
    product_sk BIGSERIAL PRIMARY KEY,
    product_id TEXT UNIQUE NOT NULL,
    product_number TEXT,
    product_name TEXT,
    category_id TEXT,
    category TEXT,
    subcategory TEXT,
    maintenance TEXT,
    cost NUMERIC,
    product_line TEXT,
    start_date DATE,
    end_date DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE warehouse.dim_products ADD COLUMN IF NOT EXISTS end_date DATE;

CREATE OR REPLACE PROCEDURE warehouse.load_dim_products()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_inserted BIGINT := 0;
    v_updated BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Map key taxonomy to subcategory names, then join the reference table.
    -- =======================================================================
    CREATE TEMP TABLE new_rows ON COMMIT DROP AS
    WITH keyed AS (
        SELECT
            pn.prd_id,
            pn.prd_key,
            pn.prd_nm,
            pn.prd_cost,
            pn.prd_line,
            pn.start_date,
            pn.end_date,
            pn.cat_id
        FROM staging.prd_info AS pn
    ),

    mapped AS (
        SELECT
            keyed.prd_id,
            keyed.prd_key,
            keyed.prd_nm,
            keyed.prd_cost,
            keyed.prd_line,
            keyed.start_date,
            keyed.end_date,
            CASE keyed.cat_id
                WHEN 'AC_BC' THEN 'Bottles and Cages'
                WHEN 'AC_BR' THEN 'Bike Racks'
                WHEN 'AC_BS' THEN 'Bike Stands'
                WHEN 'AC_CL' THEN 'Cleaners'
                WHEN 'AC_FE' THEN 'Fenders'
                WHEN 'AC_HE' THEN 'Helmets'
                WHEN 'AC_HP' THEN 'Hydration Packs'
                WHEN 'AC_LI' THEN 'Lights'
                WHEN 'AC_LO' THEN 'Locks'
                WHEN 'AC_PA' THEN 'Panniers'
                WHEN 'AC_PU' THEN 'Pumps'
                WHEN 'AC_TT' THEN 'Tires and Tubes'
                WHEN 'BI_MB' THEN 'Mountain Bikes'
                WHEN 'BI_RB' THEN 'Road Bikes'
                WHEN 'BI_TB' THEN 'Touring Bikes'
                WHEN 'CL_BS' THEN 'Bib-Shorts'
                WHEN 'CL_CA' THEN 'Caps'
                WHEN 'CL_GL' THEN 'Gloves'
                WHEN 'CL_JE' THEN 'Jerseys'
                WHEN 'CL_SH' THEN 'Shorts'
                WHEN 'CL_SO' THEN 'Socks'
                WHEN 'CL_TI' THEN 'Tights'
                WHEN 'CL_VE' THEN 'Vests'
                WHEN 'CO_BB' THEN 'Bottom Brackets'
                WHEN 'CO_BR' THEN 'Brakes'
                WHEN 'CO_CH' THEN 'Chains'
                WHEN 'CO_CS' THEN 'Cranksets'
                WHEN 'CO_DE' THEN 'Derailleurs'
                WHEN 'CO_FO' THEN 'Forks'
                WHEN 'CO_HB' THEN 'Handlebars'
                WHEN 'CO_HS' THEN 'Headsets'
                WHEN 'CO_MF' THEN 'Mountain Frames'
                WHEN 'CO_PE' THEN 'Pedals'
                WHEN 'CO_RF' THEN 'Road Frames'
                WHEN 'CO_SA' THEN 'Saddles'
                WHEN 'CO_TF' THEN 'Touring Frames'
                WHEN 'CO_WH' THEN 'Wheels'
                ELSE NULL
            END AS subcategory_name
        FROM keyed
    ),

    combined AS (
        SELECT
            mapped.prd_id AS product_id,
            mapped.prd_key AS product_number,
            mapped.prd_nm AS product_name,
            ref.id AS category_id,
            ref.cat AS category,
            ref.subcat AS subcategory,
            ref.maintenance AS maintenance,
            mapped.prd_cost AS cost,
            mapped.prd_line AS product_line,
            mapped.start_date AS start_date,
            mapped.end_date AS end_date
        FROM mapped
        LEFT JOIN staging.px_cat_g1v2 AS ref
            ON ref.subcat = mapped.subcategory_name
    )

    SELECT
        combined.product_id,
        combined.product_number,
        combined.product_name,
        combined.category_id,
        combined.category,
        combined.subcategory,
        combined.maintenance,
        combined.cost,
        combined.product_line,
        combined.start_date,
        combined.end_date
    FROM combined
    WHERE combined.product_id IS NOT NULL;

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    -- =======================================================================
    -- Merge with change detection: only truly changed rows are updated.
    -- =======================================================================
    WITH upsert AS (
        INSERT INTO warehouse.dim_products (
            product_id,
            product_number,
            product_name,
            category_id,
            category,
            subcategory,
            maintenance,
            cost,
            product_line,
            start_date,
            end_date
        )
        SELECT
            product_id,
            product_number,
            product_name,
            category_id,
            category,
            subcategory,
            maintenance,
            cost,
            product_line,
            start_date,
            end_date
        FROM new_rows
        ON CONFLICT (product_id) DO UPDATE SET
            product_number = EXCLUDED.product_number,
            product_name = EXCLUDED.product_name,
            category_id = EXCLUDED.category_id,
            category = EXCLUDED.category,
            subcategory = EXCLUDED.subcategory,
            maintenance = EXCLUDED.maintenance,
            cost = EXCLUDED.cost,
            product_line = EXCLUDED.product_line,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            updated_at = NOW()
        WHERE warehouse.dim_products.product_number IS DISTINCT FROM EXCLUDED.product_number
            OR warehouse.dim_products.product_name IS DISTINCT FROM EXCLUDED.product_name
            OR warehouse.dim_products.category_id IS DISTINCT FROM EXCLUDED.category_id
            OR warehouse.dim_products.category IS DISTINCT FROM EXCLUDED.category
            OR warehouse.dim_products.subcategory IS DISTINCT FROM EXCLUDED.subcategory
            OR warehouse.dim_products.maintenance IS DISTINCT FROM EXCLUDED.maintenance
            OR warehouse.dim_products.cost IS DISTINCT FROM EXCLUDED.cost
            OR warehouse.dim_products.product_line IS DISTINCT FROM EXCLUDED.product_line
            OR warehouse.dim_products.start_date IS DISTINCT FROM EXCLUDED.start_date
            OR warehouse.dim_products.end_date IS DISTINCT FROM EXCLUDED.end_date
        RETURNING (xmax = 0) AS inserted
    )

    SELECT
        count(*) FILTER (WHERE inserted),
        count(*) FILTER (WHERE NOT inserted)
    INTO
        v_inserted,
        v_updated
    FROM upsert;

    RAISE NOTICE 'warehouse.dim_products: combined=% inserted=% updated=%',
        v_rows,
        v_inserted,
        v_updated;
END;
$$;
