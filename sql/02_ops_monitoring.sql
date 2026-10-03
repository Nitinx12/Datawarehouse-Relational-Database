-- =====================================================
-- === ops monitoring: per-stage run log plus layer snapshots
-- === Apply: psql -U postgres -d datawarehouse -f sql/02_ops_monitoring.sql
-- =====================================================

CREATE SCHEMA IF NOT EXISTS ops;

-- one row per stage per run; retries overwrite the same row
CREATE TABLE IF NOT EXISTS ops.pipeline_run_log (
    run_id VARCHAR NOT NULL,
    stage VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    attempt INT,
    started_at TIMESTAMPTZ NOT NULL,
    duration_s NUMERIC(10, 1),
    rows_in BIGINT,
    rows_out BIGINT,
    rows_rejected BIGINT,
    detail JSONB,
    PRIMARY KEY (run_id, stage)
);

-- row count of every base table per layer per run
CREATE TABLE IF NOT EXISTS ops.table_snapshot (
    run_id VARCHAR NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    layer VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    row_count BIGINT NOT NULL,
    PRIMARY KEY (run_id, layer, table_name)
);

-- records row counts for every base table in the four data layers
CREATE OR REPLACE PROCEDURE ops.record_layer_snapshot(p_run_id VARCHAR)
LANGUAGE plpgsql
AS $$
DECLARE
    v_rec RECORD;
    v_count BIGINT;
BEGIN
    FOR v_rec IN
        SELECT
            table_schema,
            table_name
        FROM information_schema.tables
        WHERE table_schema IN ('source', 'staging', 'warehouse', 'analytics')
            AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE FORMAT(
            'SELECT COUNT(*) FROM %I.%I',
            v_rec.table_schema,
            v_rec.table_name
        )
        INTO v_count;

        INSERT INTO ops.table_snapshot (
            run_id,
            layer,
            table_name,
            row_count
        )
        VALUES (
            p_run_id,
            v_rec.table_schema,
            v_rec.table_name,
            v_count
        )
        ON CONFLICT (run_id, layer, table_name)
        DO UPDATE SET
            row_count = EXCLUDED.row_count,
            captured_at = NOW();
    END LOOP;
END;
$$;
