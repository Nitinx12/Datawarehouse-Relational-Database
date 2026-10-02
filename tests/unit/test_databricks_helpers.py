from datetime import UTC, datetime

from src.jobs.databricks_to_postgres import (
    detect_column,
    format_ts,
    qualified,
    watermark_filter,
)

A = datetime(2026, 8, 1, 5, 30, tzinfo=UTC)
B = datetime(2026, 9, 1, tzinfo=UTC)


def test_qualified_backticks_all_parts():
    assert (
        qualified("crm_source", "default", "orders")
        == "`crm_source`.`default`.`orders`"
    )


def test_format_ts_utc_layout():
    assert format_ts(A) == "2026-08-01 05:30:00.000000+00:00"


def test_watermark_filter_full_window():
    assert watermark_filter("updated_at", None, B) == (
        "`updated_at` <= TIMESTAMP '2026-09-01 00:00:00.000000+00:00'"
    )


def test_watermark_filter_incremental_window():
    assert watermark_filter("updated_at", A, B) == (
        "`updated_at` > TIMESTAMP '2026-08-01 05:30:00.000000+00:00' "
        "AND `updated_at` <= TIMESTAMP '2026-09-01 00:00:00.000000+00:00'"
    )


def test_detect_column_case_insensitive():
    assert (
        detect_column(["Id", "Name", "ModifiedDate"], ["updated_at", "ModifiedDate"])
        == "ModifiedDate"
    )


def test_detect_column_none_when_absent():
    assert detect_column(["x"], ["id"]) is None
