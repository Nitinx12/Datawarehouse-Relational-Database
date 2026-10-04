-- ===========================================================================
-- Script : 06_explore_warehouse_constraints
-- Purpose : maps primary keys, foreign keys, and indexes of warehouse tables.
-- Run : psql -d datawarehouse -f sql/analytics/exploration/06_explore_warehouse_constraints.sql
-- ===========================================================================

-- ===========================================================================
-- Primary-key and unique constraints in the warehouse schema.
-- ===========================================================================
SELECT
    constraints.table_name,
    constraints.constraint_name,
    constraints.constraint_type,
    key_usage.column_name,
    key_usage.ordinal_position
FROM information_schema.table_constraints AS constraints
INNER JOIN information_schema.key_column_usage AS key_usage
    ON constraints.constraint_name = key_usage.constraint_name
    AND constraints.table_schema = key_usage.table_schema
WHERE constraints.table_schema = 'warehouse'
    AND constraints.constraint_type IN ('PRIMARY KEY', 'UNIQUE')

ORDER BY
    constraints.table_name,
    constraints.constraint_name,
    key_usage.ordinal_position;

-- ===========================================================================
-- Foreign-key relationships between warehouse.fact_sales and dimensions.
-- ===========================================================================
SELECT
    constraints.table_name AS fact_table,
    key_usage.column_name AS fact_column,
    constraint_refs.table_name AS dimension_table,
    constraint_refs.column_name AS dimension_column,
    constraints.constraint_name
FROM information_schema.table_constraints AS constraints
INNER JOIN information_schema.key_column_usage AS key_usage
    ON constraints.constraint_name = key_usage.constraint_name
    AND constraints.table_schema = key_usage.table_schema
INNER JOIN information_schema.constraint_column_usage AS constraint_refs
    ON constraints.constraint_name = constraint_refs.constraint_name
    AND constraints.table_schema = constraint_refs.table_schema
WHERE constraints.table_schema = 'warehouse'
    AND constraints.constraint_type = 'FOREIGN KEY'

ORDER BY
    constraints.table_name,
    key_usage.column_name;

-- ===========================================================================
-- Indexes backing the warehouse tables.
-- ===========================================================================
SELECT
    indexes.schemaname AS table_schema,
    indexes.tablename AS table_name,
    indexes.indexname AS index_name,
    indexes.indexdef AS index_definition
FROM pg_indexes AS indexes
WHERE indexes.schemaname = 'warehouse'

ORDER BY
    indexes.tablename,
    indexes.indexname;
