from src.utils.tracking import stage_metrics


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
