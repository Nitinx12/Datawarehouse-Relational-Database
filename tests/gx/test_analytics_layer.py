# analytics layer gate with segment, KPI, and snapshot guards
import os

import pytest

psycopg = pytest.importorskip("psycopg")
gx = pytest.importorskip("great_expectations")

from scripts.setup_gx_project import layer_tables, table_specs

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
LAYER = "analytics"
MIN_EXPECTATIONS_PER_TABLE = 8


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


# snapshot mart must be validated alongside the views
def test_snapshot_table_is_covered() -> None:
    specs = table_specs()
    assert "analytics_monthly_snapshot" in specs
    assert specs["analytics_monthly_snapshot"]["layer"] == LAYER


# every analytics mart carries segment and KPI guards
def test_analytics_suites_are_production_grade() -> None:
    specs = table_specs()
    tables = layer_tables(specs, LAYER)
    assert len(tables) == 5
    for name in tables:
        assert len(specs[name]["expectations"]) >= MIN_EXPECTATIONS_PER_TABLE, name


# analytics checkpoint holds exactly its layer validations
def test_analytics_checkpoint_matches_specs() -> None:
    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_ROOT))
    specs = table_specs()
    checkpoint = context.checkpoints.get(f"{LAYER}_layer")
    assert len(checkpoint.validation_definitions) == len(layer_tables(specs, LAYER))


# live analytics gate passes against postgres
@needs_pg
def test_analytics_layer_passes_gx_gate() -> None:
    from scripts.run_gx_validations import run_all

    results = {item["layer"]: item for item in run_all(include_master=False)}
    assert results[LAYER]["success"], results[LAYER]["detail"]
