-- ===========================================================================
-- Script : 05_explore_warehouse_columns
-- Purpose : details every column of every warehouse table for modeling.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/05_explore_warehouse_columns.sql
-- ===========================================================================

-- ===========================================================================
-- Full column detail for the warehouse schema.
-- ===========================================================================
SELECT
    columns.table_name,
    columns.ordinal_position,
    columns.column_name,
    columns.data_type,
    columns.is_nullable,
    columns.character_maximum_length,
    columns.numeric_precision,
    columns.numeric_scale,
    columns.column_default
FROM information_schema.columns AS columns
WHERE columns.table_schema = 'warehouse'

ORDER BY
    columns.table_name,
    columns.ordinal_position;
