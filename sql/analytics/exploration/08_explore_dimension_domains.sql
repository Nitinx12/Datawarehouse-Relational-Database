-- ===========================================================================
-- Script : 08_explore_dimension_domains
-- Purpose : lists distinct domain values of warehouse dimension attributes.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/08_explore_dimension_domains.sql
-- ===========================================================================

-- ===========================================================================
-- Customer attribute domains with row counts.
-- ===========================================================================
SELECT
    dim_customers.gender,
    dim_customers.marital_status,
    dim_customers.country,
    COUNT(*) AS customer_count
FROM warehouse.dim_customers AS dim_customers

GROUP BY
    dim_customers.gender,
    dim_customers.marital_status,
    dim_customers.country

ORDER BY
    customer_count DESC,
    dim_customers.country ASC,
    dim_customers.gender ASC,
    dim_customers.marital_status ASC;

-- ===========================================================================
-- Product attribute domains with row counts.
-- ===========================================================================
SELECT
    dim_products.category,
    dim_products.subcategory,
    dim_products.product_line,
    dim_products.maintenance,
    COUNT(*) AS product_count
FROM warehouse.dim_products AS dim_products

GROUP BY
    dim_products.category,
    dim_products.subcategory,
    dim_products.product_line,
    dim_products.maintenance

ORDER BY
    dim_products.category,
    dim_products.subcategory,
    dim_products.product_line,
    dim_products.maintenance;
