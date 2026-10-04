/*
===============================================================================
Database Metadata
===============================================================================
Database:
    datawarehouse

Purpose:
    - List all schemas in the database.
    - Count tables in each schema.
    - Count views in each schema.
    - Count total objects in each schema.
    - Provide a high-level overview of the database structure.

PostgreSQL
===============================================================================
*/

-- =============================================================================
-- 1. Database information
-- =============================================================================

SELECT
    current_database() AS database_name,
    current_user AS database_user,
    version() AS database_version;


-- =============================================================================
-- 2. Schema-level object summary
-- =============================================================================

SELECT
    n.nspname AS schema_name,
    count(*) FILTER (
        WHERE c.relkind IN ('r', 'p')
    ) AS table_count,
    count(*) FILTER (
        WHERE c.relkind IN ('v', 'm')
    ) AS view_count,
    count(*) FILTER (
        WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
    ) AS total_objects
FROM pg_catalog.pg_namespace AS n
LEFT JOIN pg_catalog.pg_class AS c
    ON n.oid = c.relnamespace
    AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
WHERE n.nspname NOT IN (
    'pg_catalog',
    'information_schema'
)
AND n.nspname NOT LIKE 'pg_%'
GROUP BY
    n.nspname
ORDER BY
    n.nspname;


-- =============================================================================
-- 3. List all schemas
-- =============================================================================

SELECT
    schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN (
    'pg_catalog',
    'information_schema'
)
AND schema_name NOT LIKE 'pg_%'
ORDER BY schema_name;
