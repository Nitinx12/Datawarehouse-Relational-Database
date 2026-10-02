-- ===========================================================================
-- Script : 07_explore_warehouse_counts_sizes
-- Purpose : compares row counts and disk sizes across warehouse tables.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/07_explore_warehouse_counts_sizes.sql
-- ===========================================================================

-- ===========================================================================
-- Exact row counts for every warehouse table.
-- ===========================================================================
SELECT
    'dim_customers'::VARCHAR AS table_name,
    COUNT(*) AS row_count
FROM warehouse.dim_customers

UNION ALL

SELECT
    'dim_products'::VARCHAR AS table_name,
    COUNT(*) AS row_count
FROM warehouse.dim_products

UNION ALL

SELECT
    'fact_sales'::VARCHAR AS table_name,
    COUNT(*) AS row_count
FROM warehouse.fact_sales

ORDER BY
    table_name;

-- ===========================================================================
-- Disk size per warehouse table, largest first.
-- ===========================================================================
SELECT
    tables.schemaname AS table_schema,
    tables.relname AS table_name,
    PG_SIZE_PRETTY(PG_TOTAL_RELATION_SIZE(tables.relid)) AS total_size,
    PG_SIZE_PRETTY(PG_RELATION_SIZE(tables.relid)) AS table_size,
    PG_SIZE_PRETTY(PG_TOTAL_RELATION_SIZE(tables.relid) - PG_RELATION_SIZE(tables.relid)) AS index_size
FROM pg_catalog.pg_statio_user_tables AS tables
WHERE tables.schemaname = 'warehouse'

ORDER BY
    PG_TOTAL_RELATION_SIZE(tables.relid) DESC;
