-- ===========================================================================
-- Procedure : analytics.load_monthly_kpi_snapshot
-- Purpose : freezes the monthly sales trend into immutable month-end history.
-- Deploy : psql -d datawarehouse -f sql/analytics/reporting_tables/monthly_kpi_snapshot.sql
-- Run : CALL analytics.load_monthly_kpi_snapshot();
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.monthly_kpi_snapshot (
    snapshot_month DATE PRIMARY KEY,
    order_count BIGINT NOT NULL,
    line_count BIGINT NOT NULL,
    total_revenue NUMERIC,
    total_quantity NUMERIC,
    customer_count BIGINT NOT NULL,
    product_count BIGINT NOT NULL,
    new_customer_count BIGINT NOT NULL,
    avg_order_revenue NUMERIC,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE PROCEDURE analytics.load_monthly_kpi_snapshot()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows BIGINT := 0;
BEGIN
    INSERT INTO analytics.monthly_kpi_snapshot (
        snapshot_month,
        order_count,
        line_count,
        total_revenue,
        total_quantity,
        customer_count,
        product_count,
        new_customer_count,
        avg_order_revenue,
        loaded_at
    )
    SELECT
        monthly_trend.order_month,
        monthly_trend.order_count,
        monthly_trend.line_count,
        monthly_trend.total_revenue,
        monthly_trend.total_quantity,
        monthly_trend.customer_count,
        monthly_trend.product_count,
        monthly_trend.new_customer_count,
        monthly_trend.avg_order_revenue,
        NOW()
    FROM analytics.report_sales_monthly AS monthly_trend
    ON CONFLICT (snapshot_month) DO UPDATE SET
        order_count = EXCLUDED.order_count,
        line_count = EXCLUDED.line_count,
        total_revenue = EXCLUDED.total_revenue,
        total_quantity = EXCLUDED.total_quantity,
        customer_count = EXCLUDED.customer_count,
        product_count = EXCLUDED.product_count,
        new_customer_count = EXCLUDED.new_customer_count,
        avg_order_revenue = EXCLUDED.avg_order_revenue,
        loaded_at = NOW();

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    RAISE NOTICE 'analytics.monthly_kpi_snapshot: upserted=% months', v_rows;
END;
$$;
