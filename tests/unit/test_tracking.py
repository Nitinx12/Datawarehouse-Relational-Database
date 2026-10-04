import os

from src.utils.tracking import resolve_run_id, stage_metrics


# aggregates load rows into row counts
def test_stage_metrics_load() -> None:
    rows = [
        {
            "name": "staging.load_a",
            "status": "SUCCESS",
            "staged": 10,
            "inserted": 6,
            "updated": 4,
            "skipped": 1,
        },
        {
            "name": "staging.load_b",
            "status": "SUCCESS",
            "staged": 5,
            "inserted": 5,
            "updated": 0,
            "skipped": 0,
        },
    ]
    metrics = stage_metrics("staging", rows)
    assert metrics["rows_in"] == 15
    assert metrics["rows_out"] == 15
    assert metrics["rows_rejected"] == 1


# counts dq and gx failures in test stages
def test_stage_metrics_tests() -> None:
    rows = [
        {"name": "dq source", "status": "SUCCESS"},
        {"name": "gx source", "status": "FAILED"},
    ]
    metrics = stage_metrics("source-tests", rows)
    assert metrics["detail"]["dq_failed"] == 0
    assert metrics["detail"]["gx_failed"] == 1
    assert "rows_in" not in metrics


# prefers explicit run id over airflow context
def test_resolve_run_id_prefers_warehouse() -> None:
    os.environ["WAREHOUSE_RUN_ID"] = "manual__wp1"
    os.environ["AIRFLOW_CTX_DAG_RUN_ID"] = "airflow__other"
    try:
        assert resolve_run_id() == "manual__wp1"
    finally:
        os.environ.pop("WAREHOUSE_RUN_ID", None)
        os.environ.pop("AIRFLOW_CTX_DAG_RUN_ID", None)


# aggregates warehouse combined counts into real row metrics
def test_stage_metrics_warehouse() -> None:
    rows = [
        {
            "name": "warehouse.load_dim_customers",
            "status": "SUCCESS",
            "staged": 100,
            "inserted": 10,
            "updated": 5,
            "skipped": 0,
        }
    ]
    metrics = stage_metrics("warehouse", rows)
    assert metrics["rows_in"] == 100
    assert metrics["rows_out"] == 15
