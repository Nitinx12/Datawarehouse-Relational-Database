import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
gx = pytest.importorskip("great_expectations")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GX_DIR = PROJECT_ROOT
LAYERS = ["source", "staging", "warehouse", "analytics"]


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


def test_gx_layer_checkpoints_exist():
    from scripts.setup_gx_project import table_specs

    assert (GX_DIR / "gx" / "great_expectations.yml").exists()
    context = gx.get_context(mode="file", project_root_dir=str(GX_DIR))
    specs = table_specs()
    for layer in LAYERS:
        checkpoint = context.checkpoints.get(f"{layer}_layer")
        tables = {name for name, spec in specs.items() if spec["layer"] == layer}
        assert tables, f"no tables specced for layer {layer}"
        assert len(checkpoint.validation_definitions) == len(tables)


@pytest.fixture(scope="module")
def gx_layer_results() -> dict:
    from scripts.run_gx_validations import run_all

    return {item["layer"]: item for item in run_all()}


@pytest.mark.parametrize("layer", LAYERS)
@needs_pg
def test_layer_passes_gx_gate(layer: str, gx_layer_results: dict):
    result = gx_layer_results[layer]
    assert result["success"], (result["name"], result["detail"])
