# master quality gate spanning every layer plus cross-mart reconciliation
import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
gx = pytest.importorskip("great_expectations")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAYERS = ["source", "staging", "warehouse", "analytics"]


# postgres must be reachable for live gate tests
def pg_available() -> bool:
    try:
        conn = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "datawarehouse"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            connect_timeout=5,
            autocommit=True,
        )
        conn.close()
        return True
    except Exception:  # noqa: BLE001
        return False


needs_pg = pytest.mark.skipif(not pg_available(), reason="postgres unreachable")


# reads one scalar value from postgres
def scalar(query: str) -> float:
    from src.utils.engine import read_postgres

    frame = read_postgres(query)
    return float(frame.iloc[0, 0])


# master checkpoint must exist and cover every table validation
def test_master_checkpoint_covers_all_tables() -> None:
    from scripts.setup_gx_project import table_specs

    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_ROOT))
    specs = table_specs()
    checkpoint = context.checkpoints.get("master_layer")
    assert len(checkpoint.validation_definitions) == len(specs)
    for layer in LAYERS:
        layer_checkpoint = context.checkpoints.get(f"{layer}_layer")
        assert len(layer_checkpoint.validation_definitions) >= 3, layer


# every per-layer gate plus the master gate passes in pipeline order
@pytest.mark.parametrize("layer", [*LAYERS, "master"])
@needs_pg
def test_every_gate_passes_in_order(layer: str) -> None:
    from scripts.run_gx_validations import run_all

    results = {item["layer"]: item for item in run_all(include_master=True)}
    assert results[layer]["success"], results[layer]["detail"]


# fact revenue must equal staging revenue with zero drift
@needs_pg
def test_revenue_reconciles_fact_vs_staging() -> None:
    fact_total = scalar(
        "SELECT COALESCE(SUM(sales_amount), 0) FROM warehouse.fact_sales"
    )
    staging_total = scalar(
        "SELECT COALESCE(SUM(sls_sales), 0) FROM staging.sales_details"
    )
    assert fact_total == pytest.approx(staging_total, abs=0.01)


# monthly mart revenue must equal dated fact revenue
@needs_pg
def test_monthly_revenue_reconciles_to_fact() -> None:
    mart_total = scalar(
        "SELECT COALESCE(SUM(total_revenue), 0) FROM analytics.report_sales_monthly"
    )
    fact_total = scalar(
        "SELECT COALESCE(SUM(sales_amount), 0) FROM warehouse.fact_sales WHERE order_date IS NOT NULL"
    )
    assert mart_total == pytest.approx(fact_total, abs=0.01)


# snapshot months must match the monthly trend with zero drift
@needs_pg
def test_snapshot_matches_monthly_trend() -> None:
    missing = scalar(
        "SELECT COUNT(*) FROM analytics.report_sales_monthly AS trend "
        "LEFT JOIN analytics.monthly_kpi_snapshot AS snap "
        "ON snap.snapshot_month = trend.order_month "
        "WHERE snap.snapshot_month IS NULL"
    )
    assert missing == 0
    drift = scalar(
        "SELECT COUNT(*) FROM analytics.report_sales_monthly AS trend "
        "JOIN analytics.monthly_kpi_snapshot AS snap "
        "ON snap.snapshot_month = trend.order_month "
        "WHERE snap.total_revenue IS DISTINCT FROM trend.total_revenue "
        "OR snap.order_count IS DISTINCT FROM trend.order_count "
        "OR snap.customer_count IS DISTINCT FROM trend.customer_count"
    )
    assert drift == 0


# category shares must sum to 100 within rounding tolerance
@needs_pg
def test_category_share_sums_to_100() -> None:
    drift = scalar(
        "SELECT ABS(COALESCE(SUM(percentage_of_total), 0) - 100) "
        "FROM analytics.report_category_sales"
    )
    assert drift <= 0.5


# customer KPI formulas and age buckets must stay consistent
@needs_pg
def test_customer_kpi_math_holds() -> None:
    bad_avg = scalar(
        "SELECT COUNT(*) FROM analytics.report_customers WHERE total_orders > 0 "
        "AND total_sales IS NOT NULL "
        "AND ABS(total_sales - avg_order_value * total_orders) > 0.01"
    )
    assert bad_avg == 0
    bad_age = scalar(
        "SELECT COUNT(*) FROM analytics.report_customers WHERE "
        "(age < 20 AND age_group <> 'Under 20') "
        "OR (age BETWEEN 20 AND 29 AND age_group <> '20-29') "
        "OR (age BETWEEN 30 AND 39 AND age_group <> '30-39') "
        "OR (age BETWEEN 40 AND 49 AND age_group <> '40-49') "
        "OR (age >= 50 AND age_group <> '50 and above')"
    )
    assert bad_age == 0


# product KPI formulas must stay consistent
@needs_pg
def test_product_kpi_math_holds() -> None:
    bad_avg = scalar(
        "SELECT COUNT(*) FROM analytics.report_products WHERE total_orders > 0 "
        "AND total_sales IS NOT NULL "
        "AND ABS(total_sales - avg_order_revenue * total_orders) > 0.01"
    )
    assert bad_avg == 0


# every fact row must resolve both dimension keys
@needs_pg
def test_fact_keys_fully_resolve() -> None:
    orphans = scalar(
        "SELECT COUNT(*) FROM warehouse.fact_sales "
        "WHERE product_key IS NULL OR customer_key IS NULL OR order_number IS NULL"
    )
    assert orphans == 0


# fact must preserve every staging sales line
@needs_pg
def test_rowcount_flows_staging_to_fact() -> None:
    staging_rows = scalar("SELECT COUNT(*) FROM staging.sales_details")
    fact_rows = scalar("SELECT COUNT(*) FROM warehouse.fact_sales")
    assert fact_rows == staging_rows


# fact order dates must never be future or ship-before-order
@needs_pg
def test_fact_order_dates_are_sane() -> None:
    future_orders = scalar(
        "SELECT COUNT(*) FROM warehouse.fact_sales WHERE order_date > CURRENT_DATE"
    )
    assert future_orders == 0
    ship_before_order = scalar(
        "SELECT COUNT(*) FROM warehouse.fact_sales WHERE shipping_date IS NOT NULL "
        "AND order_date IS NOT NULL AND shipping_date < order_date"
    )
    assert ship_before_order == 0
