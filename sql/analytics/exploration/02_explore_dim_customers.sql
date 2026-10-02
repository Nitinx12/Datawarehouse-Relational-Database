-- ===========================================================================
-- Script : 02_explore_dim_customers
-- Purpose : profiles the warehouse customer dimension grain and completeness.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/02_explore_dim_customers.sql
-- ===========================================================================

-- ===========================================================================
-- Row, key, and null profile of warehouse.dim_customers.
-- ===========================================================================
SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT dim_customers.customer_key) AS distinct_customer_keys,
    COUNT(DISTINCT dim_customers.cst_id) AS distinct_cst_ids,
    COUNT(dim_customers.customer_key) FILTER (WHERE dim_customers.customer_key IS NULL) AS null_customer_keys,
    COUNT(dim_customers.cst_id) FILTER (WHERE dim_customers.cst_id IS NULL) AS null_cst_ids,
    COUNT(dim_customers.gender) FILTER (WHERE dim_customers.gender IS NULL) AS null_genders,
    COUNT(dim_customers.birthdate) FILTER (WHERE dim_customers.birthdate IS NULL) AS null_birthdates,
    COUNT(dim_customers.country) FILTER (WHERE dim_customers.country IS NULL) AS null_countries,
    MIN(dim_customers.create_date) AS min_create_date,
    MAX(dim_customers.create_date) AS max_create_date,
    MAX(dim_customers.updated_at) AS max_updated_at
FROM warehouse.dim_customers AS dim_customers;

-- ===========================================================================
-- Duplicate business-key check on warehouse.dim_customers.
-- ===========================================================================
SELECT
    dim_customers.customer_key,
    COUNT(*) AS row_count
FROM warehouse.dim_customers AS dim_customers

GROUP BY
    dim_customers.customer_key

HAVING COUNT(*) > 1

ORDER BY
    row_count DESC,
    dim_customers.customer_key ASC

LIMIT 100;
