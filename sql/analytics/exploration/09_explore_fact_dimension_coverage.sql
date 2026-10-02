-- ===========================================================================
-- Script : 09_explore_fact_dimension_coverage
-- Purpose : checks fact-to-dimension key coverage for orphan and unused rows.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/09_explore_fact_dimension_coverage.sql
-- ===========================================================================

-- ===========================================================================
-- Orphan fact rows whose keys miss the dimensions.
-- ===========================================================================
SELECT
    COUNT(*) AS fact_row_count,
    COUNT(fact_sales.product_key) FILTER (WHERE dim_products.product_sk IS NULL) AS orphan_product_rows,
    COUNT(fact_sales.customer_key) FILTER (WHERE dim_customers.customer_sk IS NULL) AS orphan_customer_rows,
    COUNT(*) FILTER (WHERE fact_sales.product_key IS NULL) AS null_product_key_rows,
    COUNT(*) FILTER (WHERE fact_sales.customer_key IS NULL) AS null_customer_key_rows
FROM warehouse.fact_sales AS fact_sales
LEFT JOIN warehouse.dim_products AS dim_products
    ON fact_sales.product_key = dim_products.product_sk
LEFT JOIN warehouse.dim_customers AS dim_customers
    ON fact_sales.customer_key = dim_customers.customer_sk;

-- ===========================================================================
-- Dimension rows never referenced by warehouse.fact_sales.
-- ===========================================================================
SELECT
    'dim_customers'::VARCHAR AS dimension_table,
    COUNT(*) AS unreferenced_rows
FROM warehouse.dim_customers AS dim_customers
LEFT JOIN warehouse.fact_sales AS fact_sales
    ON dim_customers.customer_sk = fact_sales.customer_key
WHERE fact_sales.customer_key IS NULL

UNION ALL

SELECT
    'dim_products'::VARCHAR AS dimension_table,
    COUNT(*) AS unreferenced_rows
FROM warehouse.dim_products AS dim_products
LEFT JOIN warehouse.fact_sales AS fact_sales
    ON dim_products.product_sk = fact_sales.product_key
WHERE fact_sales.product_key IS NULL

ORDER BY
    dimension_table;
