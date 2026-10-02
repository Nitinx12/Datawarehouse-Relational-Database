-- ===========================================================================
-- Script : 01_explore_warehouse_inventory
-- Purpose : inventories warehouse tables before deeper exploration.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/01_explore_warehouse_inventory.sql
-- ===========================================================================

-- ===========================================================================
-- List all tables in the warehouse schema.
-- ===========================================================================
SELECT
    tables.table_schema,
    tables.table_name,
    tables.table_type
FROM information_schema.tables AS tables
WHERE tables.table_schema = 'warehouse'

ORDER BY
    tables.table_name;

-- ===========================================================================
-- List warehouse tables with column counts.
-- ===========================================================================
SELECT
    tables.table_schema,
    tables.table_name,
    tables.table_type,
    COUNT(columns.column_name) AS column_count
FROM information_schema.tables AS tables
LEFT JOIN information_schema.columns AS columns
    ON tables.table_schema = columns.table_schema
    AND tables.table_name = columns.table_name
WHERE tables.table_schema = 'warehouse'

GROUP BY
    tables.table_schema,
    tables.table_name,
    tables.table_type

ORDER BY
    tables.table_name;
