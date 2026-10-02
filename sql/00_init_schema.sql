-- Creates the datawarehouse database and its four layer schemas.
-- Run with psql: psql -U postgres -f 01_init_datawarehouse.sql
-- CREATE DATABASE
SELECT
    'CREATE DATABASE datawarehouse'
WHERE NOT EXISTS(
    SELECT 1
    FROM pg_database
    WHERE datname = 'datawarehouse'
);


BEGIN;

-- CREATE SCHEMA
CREATE SCHEMA IF NOT EXISTS source;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

-- descriptions
COMMENT ON SCHEMA source    IS 'Raw source-system landing layer. Minimal transformation.';
COMMENT ON SCHEMA staging   IS 'Data cleansing, standardization, validation and intermediate transformations.';
COMMENT ON SCHEMA warehouse IS 'Production business warehouse containing dimensions and fact tables.';
COMMENT ON SCHEMA analytics IS 'Reporting, analytical marts, KPIs and BI-facing objects.';
 
COMMIT;