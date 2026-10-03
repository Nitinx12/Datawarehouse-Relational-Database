# warehouse layer gate with surrogate, FK, and measure guards
import os

import pytest

psycopg = pytest.importorskip("psycopg")
gx = pytest.importorskip("great_expectations")

from scripts.setup_gx_project import layer_tables, table_specs

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
LAYER = "warehouse"
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


# fact query must expose date columns used by order-date checks
def test_fact_spec_covers_shipping_and_due_dates() -> None:
    specs = table_specs()
    assert "shipping_date" in specs["warehouse_fact_sales"]["columns"]
    assert "due_date" in specs["warehouse_fact_sales"]["columns"]


# every warehouse table carries key and measure guards
def test_warehouse_suites_are_production_grade() -> None:
    specs = table_specs()
    tables = layer_tables(specs, LAYER)
    assert len(tables) == 3
    for name in tables:
        assert len(specs[name]["expectations"]) >= MIN_EXPECTATIONS_PER_TABLE, name


# warehouse checkpoint holds exactly its layer validations
def test_warehouse_checkpoint_matches_specs() -> None:
    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_ROOT))
    specs = table_specs()
    checkpoint = context.checkpoints.get(f"{LAYER}_layer")
    assert len(checkpoint.validation_definitions) == len(layer_tables(specs, LAYER))


# live warehouse gate passes against postgres
@needs_pg
def test_warehouse_layer_passes_gx_gate() -> None:
    from scripts.run_gx_validations import run_all

    results = {item["layer"]: item for item in run_all(include_master=False)}
    assert results[LAYER]["success"], results[LAYER]["detail"]
