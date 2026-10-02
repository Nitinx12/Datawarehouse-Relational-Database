-- ===========================================================================
-- Procedure : warehouse.load_fact_sales
-- Purpose   : Full-refresh sales fact with surrogate keys resolved from
--             the dimensions. Mirrors team grain: one row per sales line,
--             LEFT JOINs preserve lines with missing dimensions.
--             Product versions share one product_number, so each line
--             takes the latest version started on or before its order
--             date, guaranteeing no fan-out. Full refresh matches team
--             view semantics on this volume.
-- Deploy    : psql -U postgres -d datawarehouse -f src/jobs/proc_warehouse_fact_sales.sql
-- Run       : CALL warehouse.load_fact_sales();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.fact_sales (
    order_number TEXT,
    product_key BIGINT REFERENCES warehouse.dim_products (product_sk),
    customer_key BIGINT REFERENCES warehouse.dim_customers (customer_sk),
    order_date DATE,
    shipping_date DATE,
    due_date DATE,
    sales_amount NUMERIC,
    quantity NUMERIC,
    price NUMERIC
);

CREATE OR REPLACE PROCEDURE warehouse.load_fact_sales()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
    v_orphan_products BIGINT := 0;
    v_orphan_customers BIGINT := 0;
BEGIN
    -- =======================================================================
    -- Full refresh: truncate, then reload every line with dimension keys.
    -- =======================================================================
    TRUNCATE TABLE warehouse.fact_sales;

    INSERT INTO warehouse.fact_sales (
        order_number,
        product_key,
        customer_key,
        order_date,
        shipping_date,
        due_date,
        sales_amount,
        quantity,
        price
    )
    SELECT
        staged.sls_ord_num AS order_number,
        dim_products.product_sk AS product_key,
        dim_customers.customer_sk AS customer_key,
        staged.sls_order_dt AS order_date,
        staged.sls_ship_dt AS shipping_date,
        staged.sls_due_dt AS due_date,
        staged.sls_sales AS sales_amount,
        staged.sls_quantity AS quantity,
        staged.sls_price AS price
    FROM staging.sales_details AS staged
    LEFT JOIN LATERAL (
        SELECT dim_products.product_sk
        FROM warehouse.dim_products AS dim_products
        WHERE dim_products.product_number = staged.sls_prd_key
        ORDER BY
            CASE
                WHEN dim_products.start_date <= staged.sls_order_dt THEN 0
                ELSE 1
            END,
            dim_products.start_date DESC
        LIMIT 1
    ) AS dim_products ON TRUE
    LEFT JOIN warehouse.dim_customers AS dim_customers
        ON dim_customers.cst_id = staged.sls_cust_id;

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    SELECT COUNT(*)
    INTO v_orphan_products
    FROM warehouse.fact_sales
    WHERE product_key IS NULL;

    SELECT COUNT(*)
    INTO v_orphan_customers
    FROM warehouse.fact_sales
    WHERE customer_key IS NULL;

    RAISE NOTICE 'warehouse.fact_sales: reloaded=% rows orphan_products=% orphan_customers=%',
        v_rows,
        v_orphan_products,
        v_orphan_customers;
END;
$$;
