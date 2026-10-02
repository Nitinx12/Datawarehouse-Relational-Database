-- ===========================================================================
-- Script : 10_explore_warehouse_samples
-- Purpose : samples the first rows of each warehouse table for eyeballing.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/10_explore_warehouse_samples.sql
-- ===========================================================================

-- ===========================================================================
-- Sample rows from warehouse.dim_customers.
-- ===========================================================================
SELECT
    dim_customers.customer_sk,
    dim_customers.customer_key,
    dim_customers.cst_id,
    dim_customers.first_name,
    dim_customers.last_name,
    dim_customers.marital_status,
    dim_customers.gender,
    dim_customers.birthdate,
    dim_customers.country,
    dim_customers.create_date,
    dim_customers.updated_at
FROM warehouse.dim_customers AS dim_customers

ORDER BY
    dim_customers.customer_sk

LIMIT 100;

-- ===========================================================================
-- Sample rows from warehouse.dim_products.
-- ===========================================================================
SELECT
    dim_products.product_sk,
    dim_products.product_id,
    dim_products.product_number,
    dim_products.product_name,
    dim_products.category_id,
    dim_products.category,
    dim_products.subcategory,
    dim_products.maintenance,
    dim_products.cost,
    dim_products.product_line,
    dim_products.start_date,
    dim_products.end_date,
    dim_products.updated_at
FROM warehouse.dim_products AS dim_products

ORDER BY
    dim_products.product_sk

LIMIT 100;

-- ===========================================================================
-- Sample rows from warehouse.fact_sales.
-- ===========================================================================
SELECT
    fact_sales.order_number,
    fact_sales.product_key,
    fact_sales.customer_key,
    fact_sales.order_date,
    fact_sales.shipping_date,
    fact_sales.due_date,
    fact_sales.sales_amount,
    fact_sales.quantity,
    fact_sales.price
FROM warehouse.fact_sales AS fact_sales

ORDER BY
    fact_sales.order_date DESC,
    fact_sales.order_number ASC

LIMIT 100;
