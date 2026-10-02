-- ===========================================================================
-- Script : 03_explore_dim_products
-- Purpose : profiles the warehouse product dimension grain and completeness.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/03_explore_dim_products.sql
-- ===========================================================================

-- ===========================================================================
-- Row, key, and cost profile of warehouse.dim_products.
-- ===========================================================================
SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT dim_products.product_id) AS distinct_product_ids,
    COUNT(DISTINCT dim_products.product_number) AS distinct_product_numbers,
    COUNT(DISTINCT dim_products.category) AS distinct_categories,
    COUNT(DISTINCT dim_products.subcategory) AS distinct_subcategories,
    COUNT(dim_products.cost) FILTER (WHERE dim_products.cost IS NULL) AS null_costs,
    COUNT(dim_products.category) FILTER (WHERE dim_products.category IS NULL) AS null_categories,
    COUNT(dim_products.product_line) FILTER (WHERE dim_products.product_line IS NULL) AS null_product_lines,
    MIN(dim_products.cost) AS min_cost,
    MAX(dim_products.cost) AS max_cost,
    AVG(dim_products.cost) AS avg_cost,
    MAX(dim_products.updated_at) AS max_updated_at
FROM warehouse.dim_products AS dim_products;

-- ===========================================================================
-- Product count per category for warehouse.dim_products.
-- ===========================================================================
SELECT
    dim_products.category,
    dim_products.subcategory,
    COUNT(*) AS product_count
FROM warehouse.dim_products AS dim_products

GROUP BY
    dim_products.category,
    dim_products.subcategory

ORDER BY
    dim_products.category,
    dim_products.subcategory;
