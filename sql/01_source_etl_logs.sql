-- builds the source.etl_logs audit table for incremental loads
BEGIN;

CREATE SCHEMA IF NOT EXISTS source;

CREATE TABLE IF NOT EXISTS source.etl_logs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT,
    job_name VARCHAR NOT NULL,
    collection_name VARCHAR NOT NULL,
    target_schema VARCHAR NOT NULL DEFAULT 'source',
    target_table VARCHAR NOT NULL,
    mode VARCHAR NOT NULL DEFAULT 'INCREMENTAL',
    watermark_column VARCHAR NOT NULL DEFAULT 'updated_at',
    watermark_from TIMESTAMPTZ,
    watermark_to TIMESTAMPTZ,
    rows_extracted BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_inserted BIGINT NOT NULL DEFAULT 0,
    rows_updated BIGINT NOT NULL DEFAULT 0,
    chunks INTEGER NOT NULL DEFAULT 0,
    status VARCHAR NOT NULL DEFAULT 'STARTED',
    validation_status VARCHAR NOT NULL DEFAULT 'N/A',
    validation_detail TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_seconds DOUBLE PRECISION GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (finished_at - started_at))) STORED
);

COMMENT ON TABLE source.etl_logs IS 'One row per source table load with watermark window and counters.';
COMMENT ON COLUMN source.etl_logs.watermark_from IS 'Exclusive lower bound of the incremental window.';
COMMENT ON COLUMN source.etl_logs.watermark_to IS 'Inclusive upper bound of the incremental window.';

ALTER TABLE source.etl_logs ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE source.etl_logs ADD COLUMN IF NOT EXISTS rows_inserted BIGINT NOT NULL DEFAULT 0;
ALTER TABLE source.etl_logs ADD COLUMN IF NOT EXISTS rows_updated BIGINT NOT NULL DEFAULT 0;
ALTER TABLE source.etl_logs ADD COLUMN IF NOT EXISTS validation_status VARCHAR NOT NULL DEFAULT 'N/A';
ALTER TABLE source.etl_logs ADD COLUMN IF NOT EXISTS validation_detail TEXT;

CREATE INDEX IF NOT EXISTS idx_etl_logs_collection_status
    ON source.etl_logs (collection_name, status, finished_at DESC);

CREATE INDEX IF NOT EXISTS idx_etl_logs_watermark_to
    ON source.etl_logs (collection_name, watermark_to DESC)
    WHERE status = 'SUCCESS';

CREATE UNIQUE INDEX IF NOT EXISTS uq_etl_logs_single_started_run
    ON source.etl_logs (job_name, collection_name)
    WHERE status = 'STARTED';

COMMIT;
